/*
 * Data for the Explore page: the filters it offers, how the active filter is
 * kept in the URL hash, and backend stories turned into ExploreItems.
 * Components only use ExploreItem, never the raw API shape.
 */
import type { Article, NewsScope, Topic } from '../types'
import {
  fetchStoryList,
  storyDate,
  storyScope,
  storyTagNames,
  toArticle,
} from './stories'
import type { ApiStory } from './stories'

/*
 * Topic, location and explainer aren't in the stories API yet. The
 * cards already show them when present, so only toExploreItem() has to change.
 */
export type ExploreItem = {
  id: string
  title: string
  imageUrl?: string // with an image the card shows it; without, it becomes a text tile
  imageAlt?: string
  topic?: Topic // no topic → neutral colours
  /** The story's tags, most relevant first (at most 3). */
  tags: string[]
  scope?: NewsScope // shown as a home or globe icon in the card's corner
  location?: string
  publisher: string
  publishedAt: Date
  isExplainer?: boolean
  /** The same story as a full post, for reading it inside the app. */
  article: Article
}

// How many stories Explore loads at a time; scrolling to the end loads the next page.
export const EXPLORE_SIZE = 20

/*
 * What Explore shows:
 * - tagIds: database tag IDs. Empty means "All". Stories with any of the tags
 *   are shown (GET /stories?tag_id=…&tag_id=…). Sorted, so the same selection
 *   always gives the same URL.
 * - query: words that must all be in the title (GET /stories?q=…). Empty means
 *   no search. With tags, only those tags' stories are searched. Only the tags
 *   are kept in the URL; the search is in memory (utils/search.ts).
 */
export type ExploreFilter = { tagIds: string[]; query: string }

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// The backend's limits for q: at least 2 characters (shorter is a 400), at most 100.
export const MIN_SEARCH_CHARS = 2
export const MAX_SEARCH_CHARS = 100

/* The search as it is sent: trimmed, single spaces, at most 100 characters; '' if too short to search. */
export function exploreQuery(text: string) {
  const query = text
    .trim()
    .replace(/\s+/g, ' ')
    .slice(0, MAX_SEARCH_CHARS)
    .trim()
  return query.length >= MIN_SEARCH_CHARS ? query : ''
}

export function exploreFilter(
  tagIds: readonly string[],
  query = '',
): ExploreFilter {
  return {
    tagIds: [
      ...new Set(
        tagIds.map((id) => id.toLowerCase()).filter((id) => UUID.test(id)),
      ),
    ].sort(),
    query: exploreQuery(query),
  }
}

/* "#explore" or "#explore?tags=<id>,<id>" */
export function isExploreHash(hash: string) {
  return hash.split('?')[0] === '#explore'
}

/* The tags in the hash, without a search. Anything that isn't a tag ID is ignored. */
export function exploreFilterFromHash(hash: string): ExploreFilter {
  const tags = new URLSearchParams(hash.split('?')[1] ?? '').get('tags')
  return exploreFilter(tags ? tags.split(',') : [])
}

/* The URL for the selected tags. The search is left out, so a refresh drops it. */
export function exploreHash(filter: Pick<ExploreFilter, 'tagIds'>) {
  const { tagIds } = exploreFilter(filter.tagIds)
  return tagIds.length ? `#explore?tags=${tagIds.join(',')}` : '#explore'
}

/* A string that changes exactly when the tags or the search do, for restarting the list. */
export function exploreFilterKey(filter: ExploreFilter) {
  return JSON.stringify([filter.tagIds, filter.query])
}

export function exploreFilterFromKey(key: string): ExploreFilter {
  const [tagIds, query] = JSON.parse(key) as [string[], string]
  return exploreFilter(tagIds, query)
}

/* The link the sidebar uses: Explore filtered by one tag. */
export function exploreTagHash(tagId: string) {
  return exploreHash({ tagIds: [tagId] })
}

/* One page of published stories, most recently updated first. */
export async function fetchExploreStories(
  filter: ExploreFilter,
  offset: number,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({
    limit: String(EXPLORE_SIZE),
    offset: String(offset),
  })
  filter.tagIds.forEach((id) => params.append('tag_id', id))
  if (filter.query) params.set('q', filter.query)
  // Signed in, stories the user translated earlier come back translated.
  return fetchStoryList(`/stories?${params}`, signal)
}

export function toExploreItem(story: ApiStory): ExploreItem {
  const lead = story.lead_article
  return {
    id: story.id,
    title: story.title,
    imageUrl: story.img_url?.trim() || undefined,
    tags: storyTagNames(story),
    scope: storyScope(story),
    publisher: lead?.provider.name ?? 'VNAANA',
    publishedAt: storyDate(story),
    // Opening a card shows this post; its "Read more" part links to the source.
    article: toArticle(story, 'dontMiss'),
  }
}
