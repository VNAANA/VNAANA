import { useSyncExternalStore } from 'react'
import { readSearch, subscribeSearch } from '../utils/search'

/* The current title search ('' when there is none). */
export function useSearch() {
  return useSyncExternalStore(subscribeSearch, readSearch, readSearch)
}
