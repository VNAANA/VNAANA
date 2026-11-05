import { useStrings } from '../../hooks/useStrings'
import { timeAgo } from '../../utils/articles'
import type { ExploreItem } from '../../utils/explore'
import styles from './ExploreCardParts.module.css'

/*
 * The headline link. Its ::after covers the whole card, so the card is one
 * click target while the link's name stays just the headline.
 */
export function CardLink({ item }: { item: ExploreItem }) {
  const { t } = useStrings()
  return (
    <a href={item.href} className={styles.link} target="_blank" rel="noopener noreferrer">
      {item.title}
      <span className="sr-only"> {t.common.opensInNewTab}</span>
    </a>
  )
}

/* "NOS · 2h ago" */
export function CardMeta({ item }: { item: ExploreItem }) {
  const { t } = useStrings()
  return (
    <p className={styles.meta}>
      <span className={styles.publisher}>{item.publisher}</span>
      {' · '}
      <time dateTime={item.publishedAt.toISOString()}>{timeAgo(item.publishedAt, t)}</time>
    </p>
  )
}
