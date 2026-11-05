/*
 * Data for the Explore page: the filters it offers, how the active filter is
 * kept in the URL hash, and backend articles turned into ExploreItems.
 * Components only use ExploreItem, never the raw API shape.
 */
import type { Topic } from '../types'
import { apiUrl } from './api'
import type { ApiArticle } from './articles'

/*
 * Image, topic, location and explainer aren't in the articles API yet. The
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

// The most GET /articles/random allows.
export const EXPLORE_SIZE = 20

/*
 * Each filter's extra query for GET /articles/random. Only "All" exists for now:
 * the API has no trending, location or topic filter on articles yet.
 * Add a filter here (and its label in strings.ts) once the backend supports it.
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

/* A random selection of articles; every call returns a different set. */
export async function fetchExploreArticles(filter: ExploreFilter, signal?: AbortSignal) {
  const response = await fetch(apiUrl(`/articles/random?limit=${EXPLORE_SIZE}${FILTER_QUERY[filter]}`), { signal })
  if (!response.ok) throw new Error('Explore request failed')
  const articles: ApiArticle[] = await response.json()
  return articles.map(toExploreItem)
}

export function toExploreItem(article: ApiArticle): ExploreItem {
  return {
    id: article.id,
    title: article.title,
    publisher: article.provider.name,
    publishedAt: new Date(article.published_at ?? article.first_seen_at),
    // There's no article page in the app yet, so the card opens the original article.
    href: article.canonical_url,
  }
}
