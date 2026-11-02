import { createContext, useContext } from 'react'
import type { Carousel } from '../../hooks/useCarousel'
import type { NovaChat } from '../../hooks/useNovaChat'
import type { Story } from '../../types'
import type { PostActions } from './usePostActions'

/*
 * Everything the pieces of a post need: the story, the shared carousel state,
 * the reaction handlers and the Ask Nova conversation. FeedPost provides it;
 * the pieces read it with usePost().
 */
export type PostContextValue = {
  story: Story
  carousel: Carousel
  actions: PostActions
  chat: NovaChat
  /** Goes up by one each time an Ask Nova button asks for the chat input to be focused. */
  composerFocusRequest: number
  titleId: string
  partIds: string[]
  /** Labels of this story's parts, in carousel order. */
  partLabels: string[]
}

export const PostContext = createContext<PostContextValue | null>(null)

export function usePost() {
  const context = useContext(PostContext)
  if (!context) throw new Error('usePost must be used inside <FeedPost>')
  return context
}

export type PartKey = 'whatHappened' | 'why' | 'fullArticle' | 'readMore'

export const PART_LABELS: Record<PartKey, string> = {
  whatHappened: 'What happened',
  why: 'Why it matters',
  fullArticle: 'Full article',
  readMore: 'Read more',
}

/*
 * The parts of a story's carousel, in order. "Full article" only appears when
 * the article text has been scraped. "Read more" (with the Ask Nova chat) is always last.
 */
export function getParts(story: Story): PartKey[] {
  return story.content?.length
    ? ['whatHappened', 'why', 'fullArticle', 'readMore']
    : ['whatHappened', 'why', 'readMore']
}
