import { useStrings } from '../../hooks/useStrings'
import { TOPIC_ICONS } from '../../data/topics'
import type { ExploreItem } from '../../utils/explore'
import { topicColorStyle } from '../../utils/topicColors'
import { CardLink, CardMeta } from './ExploreCardParts'
import styles from './ExploreTextTile.module.css'

/* A story without an image: a tile in the topic's colour where the headline is the visual. */
export function ExploreTextTile({ item }: { item: ExploreItem }) {
  const { t } = useStrings()
  const Icon = item.topic && TOPIC_ICONS[item.topic]
  // "POLITICS · EINDHOVEN"
  const label = [item.topic && t.topics[item.topic], item.location].filter(Boolean).join(' · ')

  return (
    <article className={styles.tile} style={topicColorStyle(item.topic)}>
      {(label || item.isExplainer) && (
        <div className={styles.top}>
          {label && (
            <p className={styles.topic}>
              {Icon && <Icon size={14} aria-hidden="true" />}
              {label}
            </p>
          )}
          {item.isExplainer && <span className={styles.badge}>{t.explore.explainer}</span>}
        </div>
      )}
      <h2 className={styles.title}>
        <CardLink item={item} />
      </h2>
      <CardMeta item={item} />
    </article>
  )
}
