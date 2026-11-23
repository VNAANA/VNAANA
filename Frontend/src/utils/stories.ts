/*
 * Stories from the backend, turned into the Article shape the feed uses.
 * A story's text (title, context, image) comes from the stories table; the
 * description, publisher and link come from its lead article (the primary one).
 * The story summary isn't shown yet.
 */
import type { Article, FeedReason } from '../types'
import { apiUrl } from './api'
import { supabase } from './supabase'

/* The parts of the backend's StoryCardRead response that the app uses. */
export type ApiStory = {
  id: string
  title: string
  context: string | null
  img_url: string | null
  articles_count: number
  first_published_at: string | null
  last_updated_at: string
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

/* Published stories, most recently updated first. */
export async function fetchStories(offset: number, limit: number, signal?: AbortSignal): Promise<ApiStory[]> {
  const response = await fetch(apiUrl(`/stories?limit=${limit}&offset=${offset}`), { signal })
  if (!response.ok) throw new Error('Stories request failed')
  return response.json()
}

/*
 * The personal "For you" stories, or null when there is no personal feed:
 * signed out, no consent, not enough reading history yet ("locked"), or the
 * request failed. The caller then shows the general stories instead.
 */
export async function fetchForYouStories(offset: number, limit: number, signal?: AbortSignal): Promise<ApiStory[] | null> {
  const token = (await supabase.auth.getSession()).data.session?.access_token
  if (!token) return null
  let response: Response
  try {
    response = await fetch(apiUrl(`/stories/for-you?limit=${limit}&offset=${offset}`), {
      headers: { Authorization: `Bearer ${token}` },
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    return null
  }
  if (!response.ok) return null
  const feed: ApiFeed = await response.json()
  return feed.status === 'available' ? feed.stories.map((ranked) => ranked.story) : null
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
  return { stories: await fetchStories(offset, FEED_PAGE_SIZE, signal), personal: false }
}

export function toArticle(story: ApiStory, feedReason: FeedReason = 'forYou'): Article {
  const lead = story.lead_article
  const description = htmlToText(lead?.description ?? null)
  const context = toParagraphs(story.context)
  const imageUrl = story.img_url?.trim() || lead?.img_url?.trim()
  const publisherName = lead?.provider.name ?? 'VNAANA'
  // Nova reads the story's linked articles on the backend. Only the lead
  // article's publisher is known here, so other sources show their domain.
  const leadUrl = lead?.canonical_url.trim()

  return {
    id: story.id,
    ...(story.articles_count > 0 ? {
      novaStory: {
        storyId: story.id,
        sourceLabels: leadUrl ? { [leadUrl]: publisherName } : {},
      },
    } : {}),
    publisher: {
      name: publisherName,
      initials: initials(publisherName),
      verified: lead?.provider.reliability_status === 'verified',
    },
    author: lead?.author ?? undefined,
    publishedAt: storyDate(story),
    tags: story.tags.slice(0, MAX_TAGS).map((link) => link.tag.name),
    feedReason,
    title: story.title,
    ...(imageUrl ? { image: { src: imageUrl, alt: story.title } } : {}),
    summary: shorten(description),
    context: context.length > 0 ? context : undefined,
    aiNote: { sourceCount: Math.max(1, story.articles_count) },
    readMore: {
      url: lead?.canonical_url ?? '',
      readMinutes: readMinutes(story.context),
      perspectives: [],
    },
  }
}

/* When a story first went out; stories that were never published use their last update. */
export function storyDate(story: ApiStory) {
  return new Date(story.first_published_at ?? story.last_updated_at)
}

/* RSS descriptions often contain HTML. DOMParser never runs scripts, so this is safe. */
function htmlToText(html: string | null) {
  if (!html) return ''
  const text = new DOMParser().parseFromString(html, 'text/html').body.textContent ?? ''
  return text.replace(/\s+/g, ' ').trim()
}

/* Cut long text at the last full sentence that fits. */
function shorten(text: string, max = SUMMARY_MAX_CHARS) {
  if (text.length <= max) return text
  const cut = text.slice(0, max)
  const sentenceEnd = cut.lastIndexOf('. ')
  return sentenceEnd > max / 2 ? cut.slice(0, sentenceEnd + 1) : `${cut.slice(0, cut.lastIndexOf(' '))}…`
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
  if (words.length === 1) return words[0].length <= 3 ? words[0].toUpperCase() : words[0].slice(0, 2).toUpperCase()
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
