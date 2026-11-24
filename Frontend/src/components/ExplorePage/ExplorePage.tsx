import { useCallback, useEffect, useRef, useState } from 'react'
import { useExploreArticles } from '../../hooks/useExploreArticles'
import { useLoadMoreTrigger } from '../../hooks/useInfiniteList'
import { tagLabel } from '../../data/tags'
import { useStrings } from '../../hooks/useStrings'
import { useTags } from '../../hooks/useTags'
import { useSearch } from '../../hooks/useSearch'
import { exploreFilterKey, exploreHash } from '../../utils/explore'
import { setSearch } from '../../utils/search'
import {
  canMorph,
  imagesDecoded,
  withViewTransition,
} from '../../utils/viewTransition'
import type { ExploreFilter } from '../../utils/explore'
import { ExploreFilters } from './ExploreFilters'
import { ExploreGrid } from './ExploreGrid'
import { ExploreReader } from './ExploreReader'
import type { ReaderPosition } from './ExploreReader'
import { MORPH_NAME, OpenStoryContext } from './OpenStoryContext'
import { ExploreSkeleton } from './ExploreSkeleton'
import styles from './ExplorePage.module.css'

/*
 * The Explore page: header, tag filter and a masonry grid of the latest stories.
 * The tags come from the URL; the title search from the search bar.
 */
export function ExplorePage({ filter: fromHash }: { filter: ExploreFilter }) {
  const { t } = useStrings()
  const { tags } = useTags()
  const query = useSearch()
  const filter: ExploreFilter = { tagIds: fromHash.tagIds, query }
  const {
    items,
    status,
    reload,
    loadMore,
    loadingMore,
    loadMoreFailed,
    hasMore,
  } = useExploreArticles(filter)
  const pageRef = useRef<HTMLElement>(null)
  const loadMoreRef = useLoadMoreTrigger(
    pageRef,
    loadMore,
    items.length,
    status === 'ready' && hasMore && !loadMoreFailed,
  )

  // The tags live in the hash, so they survive a refresh and can be shared. The search doesn't.
  const selectTags = (tagIds: string[]) => {
    window.location.hash = exploreHash({ tagIds })
  }

  /*
   * The reader: a story opened from the grid, shown as a full post.
   * It belongs to the list it was opened from; when the tags or search change
   * (from the sidebar), that list is gone and the reader with it.
   */
  const listKey = exploreFilterKey(filter)
  const [reader, setReader] = useState<{
    storyId: string
    listKey: string
  } | null>(null)
  const [morphId, setMorphId] = useState<string | null>(null)
  // The list changed under an open reader: forget it, so going back to the old tags doesn't reopen it.
  if (reader !== null && reader.listKey !== listKey) setReader(null)
  const readerOpen = reader !== null && reader.listKey === listKey
  // Set by the reader: the story whose post is on screen now.
  const onScreenRef = useRef<ReaderPosition | null>(null)

  const openStory = useCallback(
    (storyId: string, card: HTMLElement) => {
      // A history entry, so the browser's / phone's back button closes the reader.
      window.history.pushState({ exploreReader: true }, '')
      // The card and the post share a name, so the browser animates one into the other.
      const morph = canMorph()
      if (morph) card.style.viewTransitionName = MORPH_NAME
      const transition = withViewTransition(
        () => {
          card.style.viewTransitionName = ''
          setMorphId(morph ? storyId : null)
          setReader({ storyId, listKey })
        },
        // Let the post's image decode first, so the card doesn't grow into a post without its picture.
        () =>
          imagesDecoded(
            document.querySelector(
              `[data-story-slide="${CSS.escape(storyId)}"] [data-post]`,
            ),
          ),
      )
      void transition?.finished.finally(() => setMorphId(null))
    },
    [listKey],
  )

  // Back to the grid, shrinking the post being read into its card (scrolled into view).
  const closeReader = useCallback(() => {
    const { storyId, post } = onScreenRef.current?.() ?? {
      storyId: '',
      post: null,
    }
    const card =
      pageRef.current
        ?.querySelector(`[data-story-card="${CSS.escape(storyId)}"]`)
        ?.closest<HTMLElement>('article') ?? null
    const morph = canMorph() && post !== null && card !== null
    if (morph) post.style.viewTransitionName = MORPH_NAME
    const transition = withViewTransition(
      () => {
        setReader(null)
        if (post) post.style.viewTransitionName = ''
        card?.scrollIntoView({ block: 'nearest' })
        if (morph) card.style.viewTransitionName = MORPH_NAME
      },
      // A lazy card image that was off screen loads now; wait for it like on opening.
      () => imagesDecoded(card),
    )
    const done = () => {
      if (card) card.style.viewTransitionName = ''
      // Keyboard focus goes back to the card of the story that was read last.
      card
        ?.querySelector<HTMLElement>('[data-story-card]')
        ?.focus({ preventScroll: true })
    }
    if (transition) void transition.finished.finally(done)
    else done()
  }, [])

  // Back / Esc in the reader go through history.back(), using up the entry added on opening;
  // the popstate below then closes it, the same way as the browser's back button.
  const requestClose = () => {
    if (window.history.state?.exploreReader) window.history.back()
    else closeReader()
  }

  useEffect(() => {
    if (!readerOpen) return
    window.addEventListener('popstate', closeReader)
    return () => window.removeEventListener('popstate', closeReader)
  }, [readerOpen, closeReader])

  // "Sports, Domestic" for the selected tags (only once the tags have loaded), else "All".
  const tagNames = tags
    .filter((tag) => filter.tagIds.includes(tag.id))
    .map((tag) => tagLabel(tag.name, t))
  const tagsLabel = tagNames.length ? tagNames.join(', ') : null
  const filtered = filter.tagIds.length > 0
  const searching = filter.query !== ''
  // "Titles with “flood” in Sports" while searching, else the tags (or "All").
  const sectionLabel = searching
    ? t.explore.searchSummary(filter.query, tagsLabel)
    : (tagsLabel ?? t.explore.all)

  return (
    <OpenStoryContext.Provider value={openStory}>
      {/* While a story is open the grid underneath is inert: no focus, clicks or screen reader. */}
      <main
        ref={pageRef}
        id="explore"
        className={styles.page}
        tabIndex={-1}
        aria-labelledby="explore-heading"
        inert={readerOpen}
      >
        <div className={styles.inner}>
          <header>
            <h1 id="explore-heading" className={styles.title}>
              {t.explore.title}
            </h1>
            <p className={styles.subtitle}>{t.explore.subtitle}</p>
          </header>

          <ExploreFilters
            active={filter}
            onChange={(next) => selectTags(next.tagIds)}
          />

          {/* Read out when a search starts or changes, so screen readers know what the grid now shows. */}
          {searching && (
            <p className={styles.searchSummary} role="status">
              {sectionLabel}
            </p>
          )}

          <section aria-label={sectionLabel} aria-busy={status === 'loading'}>
            {status === 'loading' && (
              <>
                <p className="sr-only" role="status">
                  {t.explore.loading}
                </p>
                <ExploreSkeleton />
              </>
            )}
            {status === 'error' && (
              <div className={styles.message} role="alert">
                <p>{t.explore.loadFailed}</p>
                <button
                  type="button"
                  className={styles.button}
                  onClick={reload}
                >
                  {t.explore.retry}
                </button>
              </div>
            )}
            {status === 'ready' && items.length === 0 && (
              <div className={styles.message}>
                <p>
                  {searching
                    ? t.explore.searchEmpty(filter.query, tagsLabel)
                    : filtered
                      ? t.explore.empty(tagsLabel ?? t.explore.all)
                      : t.explore.emptyAll}
                </p>
                <div className={styles.messageActions}>
                  {/* Searching inside some tags: try the same search in every story. */}
                  {filtered && (
                    <button
                      type="button"
                      className={styles.button}
                      onClick={() => selectTags([])}
                    >
                      {searching
                        ? t.explore.searchAllTopics
                        : t.explore.showAll}
                    </button>
                  )}
                  {searching && (
                    <button
                      type="button"
                      className={styles.button}
                      onClick={() => setSearch('')}
                    >
                      {t.explore.clearSearchShort}
                    </button>
                  )}
                </div>
              </div>
            )}
            {status === 'ready' && items.length > 0 && (
              <ExploreGrid items={items} />
            )}
            {/* Coming near this loads the next page of stories. */}
            {status === 'ready' && hasMore && (
              <div ref={loadMoreRef} aria-hidden="true" />
            )}
            {loadingMore && (
              <p className={styles.loadingMore} role="status">
                {t.explore.loadingMore}
              </p>
            )}
            {loadMoreFailed && (
              <div className={styles.message} role="alert">
                <p>{t.explore.loadMoreFailed}</p>
                <button
                  type="button"
                  className={styles.button}
                  onClick={loadMore}
                >
                  {t.explore.retry}
                </button>
              </div>
            )}
          </section>
        </div>
      </main>

      {readerOpen && (
        <ExploreReader
          items={items}
          startId={reader.storyId}
          morphId={morphId}
          hasMore={hasMore}
          loadingMore={loadingMore}
          loadMoreFailed={loadMoreFailed}
          loadMore={loadMore}
          positionRef={onScreenRef}
          onClose={requestClose}
        />
      )}
    </OpenStoryContext.Provider>
  )
}
