import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { tagIcon, tagLabel } from '../../data/tags'
import { useStrings } from '../../hooks/useStrings'
import { useTags } from '../../hooks/useTags'
import { useTopicPreferences } from '../../hooks/useTopicPreferences'
import { exploreTagHash } from '../../utils/explore'
import { orderByPreference } from '../../utils/tags'
import { Skeleton } from '../Skeleton/Skeleton'
import styles from './Navigation.module.css'

const SKELETON_ROWS = 6

/*
 * The topic list shown in the desktop sidebar and the mobile Topics sheet.
 * The tags come from the database: liked ones first, then the rest, disliked
 * last. Each one opens Explore filtered by that tag.
 */
export function TopicLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useStrings()
  const { status, tags, retry } = useTags()
  const { preferences } = useTopicPreferences()

  if (status === 'loading') {
    return (
      <ul className={styles.topicsList} aria-busy="true">
        <li className="sr-only" role="status">
          {t.topicPrefs.tagsLoading}
        </li>
        {Array.from({ length: SKELETON_ROWS }, (_, index) => (
          <li key={index} className={styles.topicRow} aria-hidden="true">
            <Skeleton width={30} height={30} />
            <Skeleton width="60%" height={12} />
          </li>
        ))}
      </ul>
    )
  }

  if (status === 'error') {
    return (
      <div className={styles.topicsError} role="alert">
        <p>{t.topicPrefs.tagsFailed}</p>
        <button type="button" className={styles.editLink} onClick={retry}>
          {t.topicPrefs.retry}
        </button>
      </div>
    )
  }

  return (
    <ul className={styles.topicsList}>
      {orderByPreference(tags, preferences).map((tag) => {
        const Icon = tagIcon(tag.name)
        const liked = preferences.liked.includes(tag.name)
        const disliked = preferences.disliked.includes(tag.name)
        return (
          <li key={tag.id}>
            <a
              href={exploreTagHash(tag.id)}
              className={styles.topicRow}
              data-disliked={disliked || undefined}
              onClick={onNavigate}
            >
              <span className={styles.topicIcon} aria-hidden="true">
                <Icon size={16} />
              </span>
              <span className={styles.topicName}>{tagLabel(tag.name, t)}</span>
              {liked && (
                <>
                  <ThumbsUp
                    size={14}
                    className={styles.likedMark}
                    aria-hidden="true"
                  />
                  <span className="sr-only">{t.topicPrefs.likedMark}</span>
                </>
              )}
              {disliked && (
                <>
                  <ThumbsDown
                    size={14}
                    className={styles.dislikedMark}
                    aria-hidden="true"
                  />
                  <span className="sr-only">{t.topicPrefs.dislikedMark}</span>
                </>
              )}
            </a>
          </li>
        )
      })}
    </ul>
  )
}
