import { createContext, useContext } from 'react'
import type { Carousel } from '../../hooks/useCarousel'
import type { NovaChat } from '../../hooks/useNovaChat'
import type { Article } from '../../types'
import type { PostActions } from './usePostActions'

/*
 * Everything the pieces of a post need: the article, the shared carousel state,
 * the reaction handlers and the Ask Nova conversation. FeedPost provides it;
 * the pieces read it with usePost().
 */
export type PostContextValue = {
  article: Article
  carousel: Carousel
  actions: PostActions
  chat: NovaChat
  /** Goes up by one each time an Ask Nova button asks for the chat input to be focused. */
  composerFocusRequest: number
  titleId: string
  partIds: string[]
  /** Labels of this article's parts, in carousel order. */
  partLabels: string[]
}

export const PostContext = createContext<PostContextValue | null>(null)

export function usePost() {
  const context = useContext(PostContext)
  if (!context) throw new Error('usePost must be used inside <FeedPost>')
  return context
}

/* The part names are in the post strings (t.post.parts). */
export type PartKey = 'whatHappened' | 'why' | 'fullArticle' | 'readMore'

/*
 * The parts of an article's carousel, in order. "Full article" only appears when
 * the article text has been scraped. "Read more" (with the Ask Nova chat) is always last.
 */
export function getParts(article: Article): PartKey[] {
  return article.content?.length
    ? ['whatHappened', 'why', 'fullArticle', 'readMore']
    : ['whatHappened', 'why', 'readMore']
}
