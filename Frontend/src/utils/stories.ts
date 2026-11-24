/*
 * Stories from the backend, turned into the Article shape the feed uses.
 * A story's text (title, summary, context, image) comes from the stories table,
 * or its saved translation; the description, publisher and link come from its
 * lead article (the primary one). The description is on the post's first part,
 * the story summary on the "Why it matters" part.
 */
import type { Article, FeedReason, NewsScope } from '../types'
import { apiUrl } from './api'
import { isLanguage } from './language'
import { supabase } from './supabase'

/* The parts of the backend's StoryCardRead response that the app uses. */
export type ApiStory = {
  id: string
  title: string
  /**
   * The story's own summary; null (or missing) until one is written. When the
   * user translated the story, the backend sends the saved translation instead.
   */
  summary?: string | null
  context: string | null
  img_url: string | null
  articles_count: number
  first_published_at: string | null
  last_updated_at: string
  /** Set when the whole story was translated into this language (the Translate button). */
  translated_into?: string | null
  tags: { tag: { id: string; name: string }; relevance_score: number | null }[]
  lead_article: {
    id: string
    title: string
    canonical_url: string
    description: string | null
    img_url: string | null
    author: string | null
    published_at: string | null
    provider: { name: string; reliability_status: string }
  } | null
}

type ApiFeed = {
  status: 'available' | 'not_logged_in' | 'no_consent' | 'locked'
  stories: { story: ApiStory; score: number }[]
}

export type StoryPage = { stories: ApiStory[]; personal: boolean }

/* How many posts the feed loads at a time; scrolling near the end loads the next page. */
export const FEED_PAGE_SIZE = 10

const SUMMARY_MAX_CHARS = 320
const WORDS_PER_MINUTE = 200
const MAX_TAGS = 3

async function accessToken() {
  return (await supabase.auth.getSession()).data.session?.access_token ?? null
}

/*
 * A list of stories from GET /stories. Signed in, the token is sent so stories
 * the user translated earlier come back translated. A token the backend
 * refuses (401) shouldn't empty the feed, so then it asks again without one.
 */
export async function fetchStoryList(
  path: string,
  signal?: AbortSignal,
): Promise<ApiStory[]> {
  const token = await accessToken()
  let response = await fetch(apiUrl(path), {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    signal,
  })
  if (token && response.status === 401)
    response = await fetch(apiUrl(path), { signal })
  if (!response.ok) throw new Error('Stories request failed')
  return response.json()
}

/* Published stories, most recently updated first. */
export function fetchStories(
  offset: number,
  limit: number,
  signal?: AbortSignal,
): Promise<ApiStory[]> {
  return fetchStoryList(`/stories?limit=${limit}&offset=${offset}`, signal)
}

/** Why Translate failed: the translation service is down or out of quota, or anything else. */
export class TranslateError extends Error {
  readonly code: 'unavailable' | 'failed'

  constructor(code: 'unavailable' | 'failed') {
    super(`Translate failed: ${code}`)
    this.code = code
  }
}

/*
 * The post's Translate button: POST /stories/{id}/translation. The backend
 * translates the story and its lead article's description into the user's
 * profile language, saves it, and returns the translated story.
 */
export async function translateStory(storyId: string): Promise<ApiStory> {
  const token = await accessToken()
  if (!token) throw new TranslateError('failed')
  let response: Response
  try {
    response = await fetch(
      apiUrl(`/stories/${encodeURIComponent(storyId)}/translation`),
      { method: 'POST', headers: { Authorization: `Bearer ${token}` } },
    )
  } catch {
    throw new TranslateError('failed')
  }
  if (response.status === 503) throw new TranslateError('unavailable')
  if (!response.ok) throw new TranslateError('failed')
  return response.json()
}

/*
 * The personal "For you" stories, or null when there is no personal feed:
 * signed out, no consent, not enough reading history yet ("locked"), or the
 * request failed. The caller then shows the general stories instead.
 */
export async function fetchForYouStories(
  offset: number,
  limit: number,
  signal?: AbortSignal,
): Promise<ApiStory[] | null> {
  const token = await accessToken()
  if (!token) return null
  let response: Response
  try {
    response = await fetch(
      apiUrl(`/stories/for-you?limit=${limit}&offset=${offset}`),
      {
        headers: { Authorization: `Bearer ${token}` },
        signal,
      },
    )
  } catch (error) {
    if (signal?.aborted) throw error
    return null
  }
  if (!response.ok) return null
  const feed: ApiFeed = await response.json()
  return feed.status === 'available'
    ? feed.stories.map((ranked) => ranked.story)
    : null
}

/*
 * One page of the feed. The first page decides the source: the personal feed
 * when there is one, else the general stories. Later pages keep that source,
 * so the feed doesn't switch halfway through.
 */
export async function fetchFeedPage(
  offset: number,
  personal: boolean | null,
  signal?: AbortSignal,
): Promise<StoryPage> {
  if (personal !== false) {
    const stories = await fetchForYouStories(offset, FEED_PAGE_SIZE, signal)
    if (stories) return { stories, personal: true }
    // Only the first page may fall back; a later personal page failing is an error.
    if (personal) throw new Error('For you request failed')
  }
  return {
    stories: await fetchStories(offset, FEED_PAGE_SIZE, signal),
    personal: false,
  }
}

export function toArticle(
  story: ApiStory,
  feedReason: FeedReason = 'forYou',
): Article {
  const lead = story.lead_article
  const description = htmlToText(lead?.description ?? null)
  const whySummary = storySummary(story)
  const context = toParagraphs(story.context)
  const imageUrl = story.img_url?.trim() || lead?.img_url?.trim()
  const publisherName = lead?.provider.name ?? 'VNAANA'
  // Nova reads the story's linked articles on the backend. Only the lead
  // article's publisher is known here, so other sources show their domain.
  const leadUrl = lead?.canonical_url.trim()

  return {
    id: story.id,
    ...(story.articles_count > 0
      ? {
          novaStory: {
            storyId: story.id,
            sourceLabels: leadUrl ? { [leadUrl]: publisherName } : {},
          },
        }
      : {}),
    publisher: {
      name: publisherName,
      initials: initials(publisherName),
      verified: lead?.provider.reliability_status === 'verified',
    },
    author: lead?.author ?? undefined,
    publishedAt: storyDate(story),
    tags: storyTagNames(story),
    scope: storyScope(story),
    feedReason,
    ...(isLanguage(story.translated_into)
      ? { translatedInto: story.translated_into }
      : {}),
    title: story.title,
    ...(imageUrl ? { image: { src: imageUrl, alt: story.title } } : {}),
    summary: shorten(description),
    context: context.length > 0 ? context : undefined,
    ...(whySummary.length > 0 ? { whySummary } : {}),
    aiNote: { sourceCount: Math.max(1, story.articles_count) },
    readMore: {
      url: lead?.canonical_url ?? '',
      readMinutes: readMinutes(story.context),
      perspectives: [],
    },
  }
}

/*
 * The text for the "Why it matters" part: the story's summary (or its saved
 * translation), one string per paragraph. Empty when the story has none yet;
 * the part then shows its placeholder.
 */
export function storySummary(story: ApiStory): string[] {
  return (story.summary ?? '')
    .split(/\n+/)
    .map((paragraph) => htmlToText(paragraph))
    .filter((paragraph) => paragraph.length > 0)
}

/* When a story first went out; stories that were never published use their last update. */
// Tags that say where the news is from. They become an icon instead of a pill.
const SCOPE_TAGS = new Map<string, NewsScope>([
  ['domestic', 'domestic'],
  ['international', 'international'],
])

const scopeOf = (name: string) => SCOPE_TAGS.get(name.trim().toLowerCase())

/* The story's most relevant tag names (the backend sends them most relevant first), without Domestic / International. */
export function storyTagNames(story: ApiStory): string[] {
  return story.tags
    .filter((link) => !scopeOf(link.tag.name))
    .slice(0, MAX_TAGS)
    .map((link) => link.tag.name)
}

/* Domestic or international, from the most relevant of those two tags. */
export function storyScope(story: ApiStory): NewsScope | undefined {
  for (const link of story.tags) {
    const scope = scopeOf(link.tag.name)
    if (scope) return scope
  }
  return undefined
}

export function storyDate(story: ApiStory) {
  return new Date(story.first_published_at ?? story.last_updated_at)
}

/* RSS descriptions often contain HTML. DOMParser never runs scripts, so this is safe. */
function htmlToText(html: string | null) {
  if (!html) return ''
  const text =
    new DOMParser().parseFromString(html, 'text/html').body.textContent ?? ''
  return text.replace(/\s+/g, ' ').trim()
}

/* Cut long text at the last full sentence that fits. */
function shorten(text: string, max = SUMMARY_MAX_CHARS) {
  if (text.length <= max) return text
  const cut = text.slice(0, max)
  const sentenceEnd = cut.lastIndexOf('. ')
  return sentenceEnd > max / 2
    ? cut.slice(0, sentenceEnd + 1)
    : `${cut.slice(0, cut.lastIndexOf(' '))}…`
}

/* Context split into paragraphs. The "- Name, reporter" byline lines at the top are skipped. */
function toParagraphs(text: string | null) {
  return (text ?? '')
    .split(/\n+/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith('- '))
}

function initials(name: string) {
  const words = name.split(/\s+/).filter(Boolean)
  if (words.length === 1)
    return words[0].length <= 3
      ? words[0].toUpperCase()
      : words[0].slice(0, 2).toUpperCase()
  return words
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
    .toUpperCase()
}

function readMinutes(text: string | null) {
  if (!text) return undefined
  const words = text.split(/\s+/).filter(Boolean).length
  return Math.max(1, Math.round(words / WORDS_PER_MINUTE))
}
