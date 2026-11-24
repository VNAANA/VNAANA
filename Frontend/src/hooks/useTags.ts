import { useSyncExternalStore } from 'react'
import { readTags, retryTags, subscribeTags } from '../utils/tags'

/* The database tags ({ status, tags }) and a retry for when loading failed. Re-renders when they arrive. */
export function useTags() {
  const state = useSyncExternalStore(subscribeTags, readTags, readTags)
  return { ...state, retry: retryTags }
}
