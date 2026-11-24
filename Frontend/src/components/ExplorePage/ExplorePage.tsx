import { useRef } from 'react'
import { useExploreArticles } from '../../hooks/useExploreArticles'
import { useLoadMoreTrigger } from '../../hooks/useInfiniteList'
import { tagLabel } from '../../data/tags'
import { useStrings } from '../../hooks/useStrings'
import { useTags } from '../../hooks/useTags'
import { exploreHash } from '../../utils/explore'
import type { ExploreFilter } from '../../utils/explore'
import { ExploreFilters } from './ExploreFilters'
import { ExploreGrid } from './ExploreGrid'
import { ExploreSkeleton } from './ExploreSkeleton'
import styles from './ExplorePage.module.css'

/* The Explore page: header, tag filter and a masonry grid of the latest stories. */
export function ExplorePage({ filter }: { filter: ExploreFilter }) {
  const { t } = useStrings()
  const { tags } = useTags()
  const { items, status, reload, loadMore, loadingMore, loadMoreFailed, hasMore } = useExploreArticles(filter)
  const pageRef = useRef<HTMLElement>(null)
  const loadMoreRef = useLoadMoreTrigger(
    pageRef,
    loadMore,
    items.length,
    status === 'ready' && hasMore && !loadMoreFailed,
  )

  // The filter lives in the hash, so it survives a refresh and can be shared.
  const selectFilter = (next: ExploreFilter) => {
    window.location.hash = exploreHash(next)
  }

  // "Sports, Domestic" for the selected tags (only once the tags have loaded), else "All".
  const tagNames = tags.filter((tag) => filter.tagIds.includes(tag.id)).map((tag) => tagLabel(tag.name, t))
  const filterLabel = tagNames.length ? tagNames.join(', ') : t.explore.all
  const filtered = filter.tagIds.length > 0

  return (
    <main ref={pageRef} id="explore" className={styles.page} tabIndex={-1} aria-labelledby="explore-heading">
      <div className={styles.inner}>
        <header>
          <h1 id="explore-heading" className={styles.title}>
            {t.explore.title}
          </h1>
          <p className={styles.subtitle}>{t.explore.subtitle}</p>
        </header>

        <ExploreFilters active={filter} onChange={selectFilter} />

        <section aria-label={filterLabel} aria-busy={status === 'loading'}>
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
              <button type="button" className={styles.button} onClick={reload}>
                {t.explore.retry}
              </button>
            </div>
          )}
          {status === 'ready' && items.length === 0 && (
            <div className={styles.message}>
              <p>{filtered ? t.explore.empty(filterLabel) : t.explore.emptyAll}</p>
              {filtered && (
                <button type="button" className={styles.button} onClick={() => selectFilter({ tagIds: [] })}>
                  {t.explore.showAll}
                </button>
              )}
            </div>
          )}
          {status === 'ready' && items.length > 0 && <ExploreGrid items={items} />}
          {/* Coming near this loads the next page of stories. */}
          {status === 'ready' && hasMore && <div ref={loadMoreRef} aria-hidden="true" />}
          {loadingMore && (
            <p className={styles.loadingMore} role="status">
              {t.explore.loadingMore}
            </p>
          )}
          {loadMoreFailed && (
            <div className={styles.message} role="alert">
              <p>{t.explore.loadMoreFailed}</p>
              <button type="button" className={styles.button} onClick={loadMore}>
                {t.explore.retry}
              </button>
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
