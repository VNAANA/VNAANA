import { useExploreArticles } from '../../hooks/useExploreArticles'
import { useStrings } from '../../hooks/useStrings'
import { exploreHash } from '../../utils/explore'
import type { ExploreFilter } from '../../utils/explore'
import { ExploreFilters } from './ExploreFilters'
import { ExploreGrid } from './ExploreGrid'
import { ExploreSkeleton } from './ExploreSkeleton'
import styles from './ExplorePage.module.css'

/* The Explore page: header, filter chips and a masonry grid of random articles. */
export function ExplorePage({ filter }: { filter: ExploreFilter }) {
  const { t } = useStrings()
  const { items, status, reload } = useExploreArticles(filter)

  // The filter lives in the hash, so it survives a refresh and can be shared.
  const selectFilter = (next: ExploreFilter) => {
    window.location.hash = exploreHash(next)
  }

  return (
    <main id="explore" className={styles.page} tabIndex={-1} aria-labelledby="explore-heading">
      <div className={styles.inner}>
        <header>
          <h1 id="explore-heading" className={styles.title}>
            {t.explore.title}
          </h1>
          <p className={styles.subtitle}>{t.explore.subtitle}</p>
        </header>

        <ExploreFilters active={filter} onSelect={selectFilter} />

        <section aria-label={t.explore.filters[filter]} aria-busy={status === 'loading'}>
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
              <p>{filter === 'all' ? t.explore.emptyAll : t.explore.empty(t.explore.filters[filter])}</p>
              {filter !== 'all' && (
                <button type="button" className={styles.button} onClick={() => selectFilter('all')}>
                  {t.explore.showAll}
                </button>
              )}
            </div>
          )}
          {status === 'ready' && items.length > 0 && <ExploreGrid items={items} />}
        </section>
      </div>
    </main>
  )
}
