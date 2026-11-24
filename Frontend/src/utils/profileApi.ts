/*
 * Calls to the backend for the signed-in user's own profile (Backend/Presentation/routers/users.py).
 * Every call sends the current Supabase access token, so a refreshed token is always used.
 */
import { apiUrl } from './api'
import type { Language } from './language'
import { supabase } from './supabase'
import { loadTags } from './tags'

/* Tag names (as in GET /tags) the user likes and dislikes. */
export type TopicLists = { liked: string[]; disliked: string[] }

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

/*
 * Tag names only, no duplicates; a topic is never in both lists. Names the
 * database no longer has (an old "World") are kept here but never shown, and
 * are dropped the next time the topics are saved.
 */
export function cleanTopics(
  value: { liked?: unknown; disliked?: unknown } | null | undefined,
): TopicLists {
  const pick = (tags: unknown) =>
    Array.isArray(tags)
      ? [
          ...new Set(
            tags.filter(
              (tag): tag is string => typeof tag === 'string' && !!tag.trim(),
            ),
          ),
        ]
      : []
  const liked = pick(value?.liked)
  return {
    liked,
    disliked: pick(value?.disliked).filter((tag) => !liked.includes(tag)),
  }
}

export function parseProfile(raw: unknown): Profile {
  const value = (raw ?? {}) as Record<string, unknown>
  if (typeof value.id !== 'string') throw new Error('Invalid profile')
  return {
    id: value.id,
    analyticsConsent: value.analytics_consent === true,
    consentUpdatedAt:
      typeof value.consent_updated_at === 'string'
        ? value.consent_updated_at
        : null,
    onboardingCompleted: value.onboarding_completed === true,
    preferences: cleanTopics(value.preferences as TopicLists | null),
    language:
      value.language === 'en' || value.language === 'nl'
        ? value.language
        : null,
  }
}

async function request(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<unknown> {
  const accessToken =
    token ?? (await supabase.auth.getSession()).data.session?.access_token
  if (!accessToken) throw new Error('Not signed in')
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
  })
  if (!response.ok)
    throw new Error(`Request failed: ${init.method ?? 'GET'} ${path}`)
  return response.json()
}

const put = (path: string, body: unknown, token?: string) =>
  request(path, { method: 'PUT', body: JSON.stringify(body) }, token)

/** Get or create the backend profile for the signed-in Supabase user. */
export async function bootstrapProfile(
  token: string,
  signal: AbortSignal,
): Promise<Profile> {
  return parseProfile(
    await request('/users/me/bootstrap', { method: 'POST', signal }, token),
  )
}

export async function giveAnalyticsConsent(
  userId: string,
  token?: string,
): Promise<Profile> {
  return parseProfile(
    await put(`/users/${userId}/consent`, { analytics_consent: true }, token),
  )
}

export async function saveLanguage(
  userId: string,
  language: Language,
): Promise<void> {
  await request(`/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify({ language }),
  })
}

export async function completeOnboarding(userId: string): Promise<Profile> {
  return parseProfile(
    await put(`/users/${userId}/onboarding`, { onboarding_completed: true }),
  )
}

/*
 * Liked topics become the user's declared interests (PUT /tags, used by the
 * For You algorithm). Liked and disliked are both kept in preferences, so the
 * pop-up and Profile can show them again. Names the database doesn't have
 * any more are dropped from both.
 */
export async function saveTopics(
  userId: string,
  topics: TopicLists,
): Promise<void> {
  const ids = new Map((await loadTags()).map((tag) => [tag.name, tag.id]))
  const known = (names: string[]) => names.filter((name) => ids.has(name))
  const saved = { liked: known(topics.liked), disliked: known(topics.disliked) }
  await Promise.all([
    put(`/users/${userId}/tags`, {
      tag_ids: saved.liked.map((name) => ids.get(name)),
    }),
    put(`/users/${userId}/preferences`, { preferences: saved }),
  ])
}
