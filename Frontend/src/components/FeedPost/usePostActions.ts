import { useRef, useState } from 'react'
import { useReaction } from '../../hooks/useReaction'
import type { Article } from '../../types'
import { logEvent, setReaction } from '../../utils/engagement'
import type { Reaction } from '../../utils/engagement'

type Handlers = {
  onHide: () => void
  onUnhide: () => void
  onOpened: () => void
  /** Opens the Ask Nova chat in the post, optionally sending a question. */
  onAskNova: (question?: string) => void
}

/*
 * Reaction state and handlers for one post. Like, dislike and "Not interested"
 * are stored for the signed-in user (utils/engagement.ts) and shown again on
 * every page; a successful share is recorded as an event.
 */
export function usePostActions(article: Article, { onHide, onUnhide, onOpened, onAskNova }: Handlers) {
  const reaction = useReaction(article.id)
  const [saved, setSaved] = useState(false)
  const [linkCopied, setLinkCopied] = useState(false)
  // What the reaction was before "Not interested", so Undo can put it back.
  const beforeHide = useRef<Reaction | null>(null)

  // Like and dislike are mutually exclusive: picking one replaces the other; tapping it again removes it.
  const toggleReaction = (value: Reaction) => void setReaction(article.id, reaction === value ? null : value)

  // "Not interested" is a dislike: it lowers the story's tags in For You.
  const hide = () => {
    beforeHide.current = reaction
    void setReaction(article.id, 'dislike')
    onHide()
  }

  const undoHide = () => {
    void setReaction(article.id, beforeHide.current)
    beforeHide.current = null
    onUnhide()
  }

  const share = async () => {
    const url = article.readMore.url
    try {
      if (navigator.share) {
        await navigator.share({ title: article.title, url })
        void logEvent(article.id, 'share', { method: 'share_sheet' })
      } else {
        await navigator.clipboard.writeText(url)
        void logEvent(article.id, 'share', { method: 'copy_link' })
        setLinkCopied(true)
        setTimeout(() => setLinkCopied(false), 2000)
      }
    } catch {
      // The user cancelled the share sheet, or the clipboard is blocked: nothing was shared.
    }
  }

  return {
    liked: reaction === 'like',
    disliked: reaction === 'dislike',
    saved,
    linkCopied,
    toggleLike: () => toggleReaction('like'),
    toggleDislike: () => toggleReaction('dislike'),
    toggleSave: () => setSaved((value) => !value),
    hide,
    undoHide,
    share,
    markOpened: onOpened,
    askNova: onAskNova,
  }
}

export type PostActions = ReturnType<typeof usePostActions>
