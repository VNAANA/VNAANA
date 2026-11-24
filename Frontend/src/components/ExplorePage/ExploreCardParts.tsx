import { useContext } from 'react'
import { tagIcon, tagLabel } from '../../data/tags'
import { useStrings } from '../../hooks/useStrings'
import { timeAgo } from '../../utils/articles'
import type { ExploreItem } from '../../utils/explore'
import { OpenStoryContext } from './OpenStoryContext'
import styles from './ExploreCardParts.module.css'

/*
 * The headline, as a button that opens the story inside the app (the source
 * is linked from the post's "Read more"). Its ::after covers the whole card,
 * so the card is one click target while the button's name stays just the headline.
 */
export function CardLink({ item }: { item: ExploreItem }) {
  const openStory = useContext(OpenStoryContext)
  return (
    <button
      type="button"
      className={styles.link}
      data-story-card={item.id}
      aria-haspopup="dialog"
      onClick={(event) => openStory(item.id, event.currentTarget.closest('article') ?? event.currentTarget)}
    >
      {item.title}
    </button>
  )
}

/*
 * The story's tags as small pills, with the same icons and names as the
 * sidebar and feed posts. A list, so screen readers announce how many there are.
 */
export function CardTags({ item }: { item: ExploreItem }) {
  const { t } = useStrings()
  if (!item.tags.length) return null
  return (
    <ul className={styles.tags} aria-label={t.post.tags}>
      {item.tags.map((name) => {
        const Icon = tagIcon(name)
        return (
          <li key={name} className={styles.tag}>
            <Icon size={12} aria-hidden="true" />
            {tagLabel(name, t)}
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
