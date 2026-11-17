import { ThumbsUp } from 'lucide-react'
import { TAG_ICONS, TAG_NAMES } from '../../data/tags'
import type { TagName } from '../../data/tags'
import { useStrings } from '../../hooks/useStrings'
import { useTopicPreferences } from '../../hooks/useTopicPreferences'
import styles from './Navigation.module.css'

/* Every tag; liked ones first, the rest in the default order. */
function orderedTags(liked: TagName[]) {
  return [...liked, ...TAG_NAMES.filter((tag) => !liked.includes(tag))]
}

/* The topic list shown in the desktop sidebar and the mobile Topics sheet. */
export function TopicLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useStrings()
  const { liked } = useTopicPreferences().preferences
  return (
    <ul className={styles.topicsList}>
      {orderedTags(liked).map((tag) => {
        const Icon = TAG_ICONS[tag]
        const isLiked = liked.includes(tag)
        return (
          <li key={tag}>
            <a href={`#topic-${tag.toLowerCase()}`} className={styles.topicRow} onClick={onNavigate}>
              <span className={styles.topicIcon} aria-hidden="true">
                <Icon size={16} />
              </span>
              <span className={styles.topicName}>{t.tags[tag]}</span>
              {isLiked && (
                <>
                  <ThumbsUp size={14} className={styles.likedMark} aria-hidden="true" />
                  <span className="sr-only">{t.topicPrefs.likedMark}</span>
                </>
              )}
            </a>
          </li>
        )
      })}
    </ul>
  )
}
