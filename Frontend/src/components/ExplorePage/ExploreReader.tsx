import { useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent, RefObject } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useLoadMoreTrigger } from '../../hooks/useInfiniteList'
import { useStrings } from '../../hooks/useStrings'
import type { ExploreItem } from '../../utils/explore'
import { FeedPost } from '../FeedPost/FeedPost'
import { PostSkeleton } from '../FeedPost/PostSkeleton'
import { MORPH_NAME } from './OpenStoryContext'
import styles from './ExploreReader.module.css'

type Props = {
  /** Explore's stories, in the grid's order. */
  items: ExploreItem[]
  /** The story that was opened; the reader starts there. */
  startId: string
  /** The post the card is turning into during the opening animation, if any. */
  morphId: string | null
  hasMore: boolean
  loadingMore: boolean
  loadMoreFailed: boolean
  loadMore: () => void
  /** Filled in by the reader, so closing (also by the browser's back button) knows which post is on screen. */
  positionRef: RefObject<ReaderPosition | null>
  onClose: () => void
}

/* The story being read now and its post, so closing can shrink the post back into its card. */
export type ReaderPosition = () => { storyId: string; post: HTMLElement | null }

// The reader doesn't keep track of opened posts (that is only the For You briefing).
const ignoreOpened = () => {}

/*
 * Explore's stories as full posts, one screen each, like the For You feed.
 * It opens at the chosen story; scrolling goes through the rest of Explore in
 * the same order (with the same tags and search) and loads more at the end.
 * Back / Esc / the browser's back button returns to the grid.
 */
export function ExploreReader({
  items,
  startId,
  morphId,
  hasMore,
  loadingMore,
  loadMoreFailed,
  loadMore,
  positionRef,
  onClose,
}: Props) {
  const { t } = useStrings()
  const scrollRef = useRef<HTMLDivElement>(null)
  // Decided once, on opening: the fallback rise-in only when the card isn't morphing into the post.
  // (Following morphId would start the rise-in the moment the morph ends.)
  const [riseIn] = useState(() => morphId === null)
  const loadMoreRef = useLoadMoreTrigger(
    scrollRef,
    loadMore,
    items.length,
    hasMore && !loadMoreFailed,
  )

  // Start at the chosen story, before the first paint (and before the opening animation's snapshot).
  useLayoutEffect(() => {
    const scroller = scrollRef.current
    const slide = scroller?.querySelector<HTMLElement>(
      `[data-story-slide="${startId}"]`,
    )
    if (!scroller || !slide) return
    scroller.scrollTop = slide.offsetTop
    slide.querySelector<HTMLElement>('article')?.focus({ preventScroll: true })
    // Only when the reader opens; later pages must not jump back.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // The story whose post fills the screen now: the slide nearest the top.
  useLayoutEffect(() => {
    positionRef.current = () => {
      const scroller = scrollRef.current
      let best: HTMLElement | null = null
      for (const slide of scroller?.querySelectorAll<HTMLElement>(
        '[data-story-slide]',
      ) ?? []) {
        if (
          !best ||
          Math.abs(slide.offsetTop - scroller!.scrollTop) <
            Math.abs(best.offsetTop - scroller!.scrollTop)
        ) {
          best = slide
        }
      }
      return {
        storyId: best?.dataset.storySlide ?? startId,
        post: best?.querySelector<HTMLElement>('[data-post]') ?? null,
      }
    }
    return () => {
      positionRef.current = null
    }
  }, [positionRef, startId])

  const onKeyDown = (event: KeyboardEvent) => {
    // Esc inside a post's own menu only closes that menu.
    if (
      event.key !== 'Escape' ||
      (event.target as Element).closest('[role="menu"]')
    )
      return
    event.preventDefault()
    onClose()
  }

  return (
    <section
      className={styles.reader}
      aria-label={t.explore.readerLabel}
      onKeyDown={onKeyDown}
      data-animate={riseIn ? '' : undefined}
    >
      <div className={styles.bar}>
        <button type="button" className={styles.back} onClick={onClose}>
          <ArrowLeft size={20} aria-hidden="true" />
          {t.explore.backToExplore}
        </button>
      </div>

      <div ref={scrollRef} className={styles.scroller}>
        {items.map((item) => (
          <div
            key={item.id}
            className={styles.slide}
            data-story-slide={item.id}
          >
            <div
              className={styles.column}
              data-post
              style={
                item.id === morphId
                  ? { viewTransitionName: MORPH_NAME }
                  : undefined
              }
            >
              <FeedPost article={item.article} onOpened={ignoreOpened} />
            </div>
          </div>
        ))}

        {/* Coming near this loads the next page of Explore. */}
        {hasMore && !loadMoreFailed && (
          <div ref={loadMoreRef} aria-hidden="true" />
        )}
        {loadingMore && (
          <div className={styles.slide}>
            <div className={styles.column}>
              <p className="sr-only" role="status">
                {t.explore.loadingMore}
              </p>
              <PostSkeleton />
            </div>
          </div>
        )}
        {loadMoreFailed && (
          <div className={styles.message} role="alert">
            <p>{t.explore.loadMoreFailed}</p>
            <button type="button" className={styles.retry} onClick={loadMore}>
              {t.explore.retry}
            </button>
          </div>
        )}
        {!hasMore && (
          <footer className={styles.end}>
            <p>{t.explore.readerEnd}</p>
            <button type="button" className={styles.retry} onClick={onClose}>
              {t.explore.backToExplore}
            </button>
          </footer>
        )}
      </div>
    </section>
  )
}
