import { Skeleton } from '../Skeleton/Skeleton'
import postStyles from './FeedPost.module.css'
import styles from './PostSkeleton.module.css'

/* A grey post in the shape of a real one, shown while the feed loads. */
export function PostSkeleton() {
  return (
    <div className={`${postStyles.post} ${styles.skeleton}`} aria-hidden="true">
      <div className={styles.header}>
        <Skeleton circle width={40} height={40} />
        <div className={styles.lines}>
          <Skeleton width="40%" height={12} />
          <Skeleton width="25%" height={10} />
        </div>
      </div>
      <div className={styles.lines}>
        <Skeleton width="90%" height={26} />
        <Skeleton width="65%" height={26} />
      </div>
      <div className={styles.lines}>
        <Skeleton height={14} />
        <Skeleton height={14} />
        <Skeleton width="80%" height={14} />
      </div>
      <Skeleton height={220} className={styles.image} />
    </div>
  )
}
