import { useId } from 'react'
import { Check, ThumbsDown, ThumbsUp } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { TAG_NAMES } from '../../data/tags'
import type { TagName } from '../../data/tags'
import { useStrings } from '../../hooks/useStrings'
import styles from './TopicPreferences.module.css'

export type TopicLists = { liked: TagName[]; disliked: TagName[] }
type List = keyof TopicLists

/*
 * Two groups of topic chips: liked and disliked. A topic picked in one group
 * is disabled in the other, so it can never be in both.
 * Used by the topic pop-up and the profile page.
 */
export function TopicPreferencesEditor({ value, onChange }: { value: TopicLists; onChange: (next: TopicLists) => void }) {
  const toggle = (list: List, tag: TagName) => {
    const current = value[list]
    const next = current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag]
    onChange({ ...value, [list]: next })
  }

  return (
    <div className={styles.editor}>
      <TopicGroup list="liked" Icon={ThumbsUp} value={value} onToggle={toggle} />
      <TopicGroup list="disliked" Icon={ThumbsDown} value={value} onToggle={toggle} />
    </div>
  )
}

type GroupProps = {
  list: List
  Icon: LucideIcon
  value: TopicLists
  onToggle: (list: List, tag: TagName) => void
}

function TopicGroup({ list, Icon, value, onToggle }: GroupProps) {
  const { t } = useStrings()
  const hintId = useId()
  const other: List = list === 'liked' ? 'disliked' : 'liked'
  const takenText = list === 'liked' ? t.topicPrefs.inDisliked : t.topicPrefs.inLiked

  return (
    <fieldset className={styles.group} data-list={list} aria-describedby={hintId}>
      <legend className={styles.legend}>
        <Icon size={18} aria-hidden="true" />
        {t.topicPrefs[list]}
      </legend>
      <p id={hintId} className={styles.hint}>
        {list === 'liked' ? t.topicPrefs.likedHint : t.topicPrefs.dislikedHint}
      </p>
      <div className={styles.chips}>
        {TAG_NAMES.map((tag) => {
          const checked = value[list].includes(tag)
          const taken = value[other].includes(tag)
          return (
            <label key={tag} className={styles.chip}>
              <input type="checkbox" checked={checked} disabled={taken} onChange={() => onToggle(list, tag)} />
              {checked && <Check size={16} aria-hidden="true" />}
              {t.tags[tag]}
              {taken && <span className="sr-only"> {takenText}</span>}
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
