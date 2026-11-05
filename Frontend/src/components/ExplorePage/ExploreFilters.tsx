import { useStrings } from '../../hooks/useStrings'
import { EXPLORE_FILTERS } from '../../utils/explore'
import type { ExploreFilter } from '../../utils/explore'
import styles from './ExploreFilters.module.css'

type Props = {
  active: ExploreFilter
  onSelect: (filter: ExploreFilter) => void
}

/* One row of filter chips; scrolls sideways on narrow screens instead of wrapping. */
export function ExploreFilters({ active, onSelect }: Props) {
  const { t } = useStrings()
  return (
    <div className={styles.row} role="group" aria-label={t.explore.filtersLabel}>
      {EXPLORE_FILTERS.map((filter) => (
        <button
          key={filter}
          type="button"
          className={styles.chip}
          aria-pressed={filter === active}
          onClick={() => onSelect(filter)}
        >
          {t.explore.filters[filter]}
        </button>
      ))}
    </div>
  )
}
