import { useCallback } from 'react'
import {
  EXPLORE_SIZE,
  exploreFilterFromKey,
  exploreFilterKey,
  fetchExploreStories,
  toExploreItem,
} from '../utils/explore'
import type { ExploreFilter, ExploreItem } from '../utils/explore'
import { useInfiniteList } from './useInfiniteList'
import type { PageLoader } from './useInfiniteList'

/*
 * Explore's stories, newest first, EXPLORE_SIZE at a time. Starts again from
 * offset 0 when the selected tags or the search change.
 */
export function useExploreArticles(filter: ExploreFilter) {
  // The filter object is new on every render; the key only changes with the tags or search.
  const key = exploreFilterKey(filter)
  const loadPage = useCallback<PageLoader<ExploreItem, null>>(
    async (offset, _source, signal) => {
      const stories = await fetchExploreStories(
        exploreFilterFromKey(key),
        offset,
        signal,
      )
      return {
        items: stories.map(toExploreItem),
        received: stories.length,
        source: null,
        done: stories.length < EXPLORE_SIZE,
      }
    },
    [key],
  )

  return useInfiniteList(loadPage, key)
}
