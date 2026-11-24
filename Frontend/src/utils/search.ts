/*
 * The title search, shared by the search bar(s) and Explore.
 *
 * It lives only in memory, not in the URL: refreshing the page starts
 * without a search, and so does leaving Explore. Changing the tags keeps it,
 * so it then looks inside the new selection.
 */
import { exploreQuery, isExploreHash } from './explore'

let query = ''
const listeners = new Set<() => void>()

export function readSearch() {
  return query
}

/* Too-short text (under 2 characters) means no search. */
export function setSearch(text: string) {
  const next = exploreQuery(text)
  if (next === query) return
  query = next
  listeners.forEach((listener) => listener())
}

export function subscribeSearch(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/* The search belongs to Explore: on any other page it is dropped. */
export function keepSearchFor(hash: string) {
  if (!isExploreHash(hash)) setSearch('')
}

if (typeof window !== 'undefined') {
  window.addEventListener('hashchange', () => keepSearchFor(window.location.hash))
}
