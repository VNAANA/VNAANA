import { Tag } from 'lucide-react'
import { TOPIC_ICONS, topicForTag } from '../../data/topics'
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

/*
 * The story's tags as small pills, like on feed posts: a tag named like one of
 * our topics gets that topic's icon and translated name. A list, so screen
 * readers announce how many there are.
 */
export function CardTags({ item }: { item: ExploreItem }) {
  const { t } = useStrings()
  if (!item.tags.length) return null
  return (
    <ul className={styles.tags} aria-label={t.post.tags}>
      {item.tags.map((name) => {
        const topic = topicForTag(name)
        const Icon = topic ? TOPIC_ICONS[topic] : Tag
        return (
          <li key={name} className={styles.tag}>
            <Icon size={12} aria-hidden="true" />
            {topic ? t.topics[topic] : name}
          </li>
        )
      })}
    </ul>
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
