/*
 * Data for the Explore page: the filters it offers, how the active filter is
 * kept in the URL hash, and backend stories turned into ExploreItems.
 * Components only use ExploreItem, never the raw API shape.
 */
import type { Topic } from '../types'
import { apiUrl } from './api'
import { storyDate } from './stories'
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
  location?: string
  publisher: string
  publishedAt: Date
  isExplainer?: boolean
  href: string
}

// How many stories Explore loads at a time; scrolling to the end loads the next page.
export const EXPLORE_SIZE = 20

/*
 * Each filter's extra query for GET /stories. Only "All" exists for now.
 * GET /stories can already filter by tag_id, so topic filters can be added
 * here (and their label in strings.ts).
 */
const FILTER_QUERY = {
  all: '',
} satisfies Record<string, string>

export type ExploreFilter = keyof typeof FILTER_QUERY
export const EXPLORE_FILTERS = Object.keys(FILTER_QUERY) as ExploreFilter[]

/* "#explore" or "#explore?filter=science" */
export function isExploreHash(hash: string) {
  return hash.split('?')[0] === '#explore'
}

/* The filter in the hash; unknown or missing filters fall back to "all". */
export function exploreFilterFromHash(hash: string): ExploreFilter {
  const filter = new URLSearchParams(hash.split('?')[1] ?? '').get('filter')
  return EXPLORE_FILTERS.find((known) => known === filter) ?? 'all'
}

export function exploreHash(filter: ExploreFilter) {
  return filter === 'all' ? '#explore' : `#explore?filter=${filter}`
}

/* One page of published stories, most recently updated first. */
export async function fetchExploreStories(filter: ExploreFilter, offset: number, signal?: AbortSignal) {
  const query = `/stories?limit=${EXPLORE_SIZE}&offset=${offset}${FILTER_QUERY[filter]}`
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
    publisher: lead?.provider.name ?? 'VNAANA',
    publishedAt: storyDate(story),
    // There's no story page in the app yet, so the card opens the lead article.
    href: lead?.canonical_url ?? '#explore',
  }
}
