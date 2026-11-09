import { Skeleton } from '../Skeleton/Skeleton'
import gridStyles from './ExploreGrid.module.css'
import styles from './ExploreSkeleton.module.css'

// A mix of tall and short placeholders, like the real grid.
const TILE_HEIGHTS = [260, 180, 220, 300, 200, 240, 170, 280, 210]

/* Placeholder grid while the first articles load. Hidden from screen readers. */
export function ExploreSkeleton({ count = TILE_HEIGHTS.length }: { count?: number }) {
  return (
    <div className={gridStyles.grid} aria-hidden="true">
      {TILE_HEIGHTS.slice(0, count).map((height, index) => (
        <div key={index} className={styles.tile} style={{ height }}>
          <Skeleton width="40%" height={12} />
          <Skeleton height={20} className={styles.gap} />
          <Skeleton width="75%" height={20} />
          <Skeleton width="50%" height={12} className={styles.meta} />
        </div>
      ))}
    </div>
  )
}
