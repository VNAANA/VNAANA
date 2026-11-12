import { MapPin } from 'lucide-react'
import { useStrings } from '../../hooks/useStrings'
import type { ExploreItem } from '../../utils/explore'
import { topicColorStyle } from '../../utils/topicColors'
import { CardLink, CardMeta } from './ExploreCardParts'
import styles from './ExploreImageCard.module.css'

type Props = {
  item: ExploreItem
  /** Varies per card to give the grid its masonry rhythm */
  imageHeight: number
  /** The grid swaps a card with a broken image for a text tile. */
  onImageError: () => void
}

/* White card with the image on top. */
export function ExploreImageCard({ item, imageHeight, onImageError }: Props) {
  const { t } = useStrings()
  return (
    <article className={styles.card}>
      <img
        className={styles.image}
        src={item.imageUrl}
        alt={item.imageAlt || item.title}
        style={{ height: imageHeight }}
        loading="lazy"
        onError={onImageError}
      />
      <div className={styles.body}>
        {(item.topic || item.location) && (
          <p className={styles.tags}>
            {item.topic && (
              <span className={styles.topic} style={topicColorStyle(item.topic)}>
                {t.topics[item.topic]}
              </span>
            )}
            {item.location && (
              <span className={styles.location}>
                <MapPin size={14} aria-hidden="true" />
                <span className="sr-only">{t.post.location}</span>
                {item.location}
              </span>
            )}
          </p>
        )}
        <h2 className={styles.title}>
          <CardLink item={item} />
        </h2>
        <CardMeta item={item} />
      </div>
    </article>
  )
}
