import type { Article } from '../types'
import { fetchFeedPage, FEED_PAGE_SIZE, toArticle } from '../utils/stories'
import { useInfiniteList } from './useInfiniteList'
import type { PageLoader } from './useInfiniteList'

/* `source` is true for the personal "For you" feed, false for the general stories. */
const loadFeedPage: PageLoader<Article, boolean> = async (
  offset,
  personal,
  signal,
) => {
  const page = await fetchFeedPage(offset, personal, signal)
  return {
    items: page.stories.map((story) =>
      toArticle(story, page.personal ? 'forYou' : 'dontMiss'),
    ),
    received: page.stories.length,
    source: page.personal,
    done: page.stories.length < FEED_PAGE_SIZE,
  }
}

/*
 * The For you feed, FEED_PAGE_SIZE stories at a time. Signed in with a personal
 * feed: GET /stories/for-you. Otherwise (signed out, no consent, still locked):
 * the latest published stories. Starts again when the signed-in user changes,
 * and waits until the session has been checked so it doesn't load twice.
 */
export function useFeedStories(userId: string | null, sessionChecked: boolean) {
  const list = useInfiniteList(loadFeedPage, userId, sessionChecked)
  return { ...list, articles: list.items }
}
