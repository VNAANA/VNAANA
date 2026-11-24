import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useCarousel } from '../../hooks/useCarousel'
import { useNovaChat } from '../../hooks/useNovaChat'
import { useReaction } from '../../hooks/useReaction'
import { logReadComplete } from '../../utils/engagement'
import { useStrings } from '../../hooks/useStrings'
import type { Article } from '../../types'
import { PartDots } from './CarouselControls'
import { PostCarousel } from './PostCarousel'
import { getParts, PostContext } from './PostContext'
import type { PartKey } from './PostContext'
import { PostHeader } from './PostHeader'
import { ReactionBar } from './ReactionBar'
import { ContextPart, ReadMorePart, WhatHappenedPart, WhyPart } from './sections/Parts'
import { usePostActions } from './usePostActions'
import styles from './FeedPost.module.css'

type Props = {
  article: Article
  /** Called when the user opens the article (moves past part 1, reads more or asks Nova). */
  onOpened: (articleId: string) => void
}

const PART_ELEMENTS: Record<PartKey, ReactNode> = {
  whatHappened: <WhatHappenedPart />,
  why: <WhyPart />,
  context: <ContextPart />,
  readMore: <ReadMorePart />,
}

/*
 * One news article in the feed. Holds the state (carousel, reactions, Ask Nova
 * chat, hidden) and shares it with the pieces through PostContext.
 *
 * Layout: top bar, then a 3- or 4-part carousel (see getParts) whose part 1 shows the headline and
 * summary before the image (they swipe away together), progress dots, then
 * heart / share / Ask Nova.
 */
export function FeedPost({ article, onOpened }: Props) {
  const { t } = useStrings()
  const parts = getParts(article)
  const partLabels = parts.map((part) => t.post.parts[part])
  const carousel = useCarousel(parts.length)
  const chat = useNovaChat(article.novaStory)
  // A story the user marked "Not interested" earlier (a stored dislike) starts collapsed;
  // after that, their own Hide / Undo decides.
  const disliked = useReaction(article.id) === 'dislike'
  const [hiddenChoice, setHiddenChoice] = useState<boolean | null>(null)
  const hidden = hiddenChoice ?? disliked
  const [composerFocusRequest, setComposerFocusRequest] = useState(0)
  const undoRef = useRef<HTMLButtonElement>(null)
  const postRef = useRef<HTMLElement>(null)
  // Only move focus after the user's own Hide / Undo, not when a post loads collapsed.
  const focusAfterToggle = useRef(false)

  // Every Ask Nova button in the post leads here: go to the chat part,
  // focus its input, and send the question if there is one.
  const askNova = (question?: string) => {
    onOpened(article.id)
    carousel.goTo(parts.indexOf('readMore'))
    setComposerFocusRequest((n) => n + 1)
    if (question) void chat.send(question)
  }

  const actions = usePostActions(article, {
    onHide: () => {
      focusAfterToggle.current = true
      setHiddenChoice(true)
    },
    onUnhide: () => {
      focusAfterToggle.current = true
      setHiddenChoice(false)
    },
    onOpened: () => onOpened(article.id),
    onAskNova: askNova,
  })

  useEffect(() => {
    if (carousel.index > 0) onOpened(article.id)
  }, [carousel.index, onOpened, article.id])

  // Read: the reader moved past the first part (swipe, arrows, dots or Ask Nova).
  // Sent once per story; the part reached is sent along.
  useEffect(() => {
    if (carousel.index > 0) logReadComplete(article.id, carousel.index + 1, parts.length)
  }, [carousel.index, parts.length, article.id])

  // Keep keyboard focus in a sensible place when hiding / undoing.
  useEffect(() => {
    if (!focusAfterToggle.current) return
    focusAfterToggle.current = false
    if (hidden) undoRef.current?.focus()
    else postRef.current?.focus()
  }, [hidden])

  if (hidden) {
    return (
      <article className={styles.hidden} data-hidden="true" aria-label={t.post.hiddenLabel(article.title)}>
        <p>
          <strong>{t.post.hidden}</strong> · {t.post.hiddenText}
        </p>
        <button ref={undoRef} type="button" className={styles.undo} onClick={actions.undoHide}>
          {t.post.undo}
        </button>
      </article>
    )
  }

  const titleId = `${article.id}-title`
  const partIds = parts.map((_, i) => `${article.id}-part-${i + 1}`)

  return (
    <PostContext.Provider
      value={{ article, carousel, actions, chat, composerFocusRequest, titleId, partIds, partLabels }}
    >
      <article ref={postRef} className={styles.post} aria-labelledby={titleId} tabIndex={-1}>
        <PostHeader />
        <PostCarousel
          className={styles.carousel}
          // Room for the "1 / 3" pill above the text and the Why / Read more panels
          partPadding={{ top: 52 }}
          parts={parts.map((part) => PART_ELEMENTS[part])}
        />
        <div className={styles.dotsRow}>
          <PartDots />
        </div>
        <footer className={styles.actionsFooter}>
          <ReactionBar kinds={['like', 'share']} />
        </footer>
      </article>
    </PostContext.Provider>
  )
}
