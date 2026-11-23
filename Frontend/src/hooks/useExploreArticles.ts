import { useCallback } from 'react'
import { EXPLORE_SIZE, fetchExploreStories, toExploreItem } from '../utils/explore'
import type { ExploreFilter, ExploreItem } from '../utils/explore'
import { useInfiniteList } from './useInfiniteList'
import type { PageLoader } from './useInfiniteList'

/* Explore's stories, newest first, EXPLORE_SIZE at a time. Starts again when the filter changes. */
export function useExploreArticles(filter: ExploreFilter) {
  const loadPage = useCallback<PageLoader<ExploreItem, null>>(async (offset, _source, signal) => {
    const stories = await fetchExploreStories(filter, offset, signal)
    return {
      items: stories.map(toExploreItem),
      received: stories.length,
      source: null,
      done: stories.length < EXPLORE_SIZE,
    }
  }, [filter])

  return useInfiniteList(loadPage, filter)
}
