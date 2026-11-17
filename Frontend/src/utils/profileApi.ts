/*
 * Calls to the backend for the signed-in user's own profile (Backend/Presentation/routers/users.py).
 * Every call sends the current Supabase access token, so a refreshed token is always used.
 */
import { TAG_NAMES } from '../data/tags'
import type { TagName } from '../data/tags'
import { apiUrl } from './api'
import type { Language } from './language'
import { supabase } from './supabase'

export type TopicLists = { liked: TagName[]; disliked: TagName[] }

/** The fields of UserRead the frontend uses. */
export type Profile = {
  id: string
  analyticsConsent: boolean
  consentUpdatedAt: string | null
  onboardingCompleted: boolean
  preferences: TopicLists
  /** Null until the profile has a language the app supports. */
  language: Language | null
}

/* Known tags only, no duplicates, in the default tag order; a topic is never in both lists. */
export function cleanTopics(value: { liked?: unknown; disliked?: unknown } | null | undefined): TopicLists {
  const pick = (tags: unknown) => (Array.isArray(tags) ? TAG_NAMES.filter((tag) => tags.includes(tag)) : [])
  const liked = pick(value?.liked)
  return { liked, disliked: pick(value?.disliked).filter((tag) => !liked.includes(tag)) }
}

export function parseProfile(raw: unknown): Profile {
  const value = (raw ?? {}) as Record<string, unknown>
  if (typeof value.id !== 'string') throw new Error('Invalid profile')
  return {
    id: value.id,
    analyticsConsent: value.analytics_consent === true,
    consentUpdatedAt: typeof value.consent_updated_at === 'string' ? value.consent_updated_at : null,
    onboardingCompleted: value.onboarding_completed === true,
    preferences: cleanTopics(value.preferences as TopicLists | null),
    language: value.language === 'en' || value.language === 'nl' ? value.language : null,
  }
}

async function request(path: string, init: RequestInit = {}, token?: string): Promise<unknown> {
  const accessToken = token ?? (await supabase.auth.getSession()).data.session?.access_token
  if (!accessToken) throw new Error('Not signed in')
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
  })
  if (!response.ok) throw new Error(`Request failed: ${init.method ?? 'GET'} ${path}`)
  return response.json()
}

const put = (path: string, body: unknown, token?: string) =>
  request(path, { method: 'PUT', body: JSON.stringify(body) }, token)

/** Get or create the backend profile for the signed-in Supabase user. */
export async function bootstrapProfile(token: string, signal: AbortSignal): Promise<Profile> {
  return parseProfile(await request('/users/me/bootstrap', { method: 'POST', signal }, token))
}

export async function giveAnalyticsConsent(userId: string, token?: string): Promise<Profile> {
  return parseProfile(await put(`/users/${userId}/consent`, { analytics_consent: true }, token))
}

export async function saveLanguage(userId: string, language: Language): Promise<void> {
  await request(`/users/${userId}`, { method: 'PATCH', body: JSON.stringify({ language }) })
}

export async function completeOnboarding(userId: string): Promise<Profile> {
  return parseProfile(await put(`/users/${userId}/onboarding`, { onboarding_completed: true }))
}

// Tag IDs never change while the app is open; fetch them once (again after a failure).
let tagIds: Promise<Map<string, string>> | null = null

function loadTagIds() {
  tagIds ??= fetch(apiUrl('/tags'))
    .then((response) => {
      if (!response.ok) throw new Error('Could not load tags')
      return response.json() as Promise<{ id: string; name: string }[]>
    })
    .then((tags) => new Map(tags.map((tag) => [tag.name, tag.id])))
    .catch((error) => {
      tagIds = null
      throw error
    })
  return tagIds
}

/*
 * Liked topics become the user's declared interests (PUT /tags, used by the
 * For You algorithm). Liked and disliked are both kept in preferences, so the
 * pop-up and Profile can show them again.
 */
export async function saveTopics(userId: string, topics: TopicLists): Promise<void> {
  const ids = await loadTagIds()
  const likedIds = topics.liked.map((name) => ids.get(name))
  if (likedIds.some((id) => id === undefined)) throw new Error('Unknown tag')
  await Promise.all([
    put(`/users/${userId}/tags`, { tag_ids: likedIds }),
    put(`/users/${userId}/preferences`, { preferences: topics }),
  ])
}
