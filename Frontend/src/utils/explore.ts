/*
 * Data for the Explore page: the filters it offers, how the active filter is
 * kept in the URL hash, and backend stories turned into ExploreItems.
 * Components only use ExploreItem, never the raw API shape.
 */
import type { NewsScope, Topic } from '../types'
import { apiUrl } from './api'
import { storyDate, storyScope, storyTagNames } from './stories'
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
  href: string
}

// How many stories Explore loads at a time; scrolling to the end loads the next page.
export const EXPLORE_SIZE = 20

/*
 * The tags Explore is filtered by, as database tag IDs. Empty means "All".
 * Stories with any of the tags are shown (GET /stories?tag_id=…&tag_id=…).
 * The IDs are sorted, so the same selection always gives the same URL.
 */
export type ExploreFilter = { tagIds: string[] }

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function exploreFilter(tagIds: readonly string[]): ExploreFilter {
  return { tagIds: [...new Set(tagIds.map((id) => id.toLowerCase()).filter((id) => UUID.test(id)))].sort() }
}

/* "#explore" or "#explore?tags=<id>,<id>" */
export function isExploreHash(hash: string) {
  return hash.split('?')[0] === '#explore'
}

/* The filter in the hash. Anything that isn't a tag ID is ignored. */
export function exploreFilterFromHash(hash: string): ExploreFilter {
  const tags = new URLSearchParams(hash.split('?')[1] ?? '').get('tags')
  return exploreFilter(tags ? tags.split(',') : [])
}

export function exploreHash(filter: ExploreFilter) {
  const { tagIds } = exploreFilter(filter.tagIds)
  return tagIds.length ? `#explore?tags=${tagIds.join(',')}` : '#explore'
}

/* The link the sidebar uses: Explore filtered by one tag. */
export function exploreTagHash(tagId: string) {
  return exploreHash({ tagIds: [tagId] })
}

/* A string that changes exactly when the selection does, for resetting the list. */
export function exploreFilterKey(filter: ExploreFilter) {
  return filter.tagIds.join(',')
}

/* One page of published stories, most recently updated first. */
export async function fetchExploreStories(filter: ExploreFilter, offset: number, signal?: AbortSignal) {
  const params = new URLSearchParams({ limit: String(EXPLORE_SIZE), offset: String(offset) })
  filter.tagIds.forEach((id) => params.append('tag_id', id))
  const query = `/stories?${params}`
  const response = await fetch(apiUrl(query), { signal })
  if (!response.ok) throw new Error('Explore request failed')
  const stories: ApiStory[] = await response.json()
  return stories
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
    // There's no story page in the app yet, so the card opens the lead article.
    href: lead?.canonical_url ?? '#explore',
  }
}
