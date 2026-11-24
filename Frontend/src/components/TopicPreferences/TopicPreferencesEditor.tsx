import { useId } from 'react'
import { Check, ThumbsDown, ThumbsUp } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { tagIcon, tagLabel } from '../../data/tags'
import { useStrings } from '../../hooks/useStrings'
import { useTags } from '../../hooks/useTags'
import styles from './TopicPreferences.module.css'

/* Tag names (as in GET /tags). */
export type TopicLists = { liked: string[]; disliked: string[] }
type List = keyof TopicLists

/*
 * Two groups of topic chips: liked and disliked. A topic picked in one group
 * is disabled in the other, so it can never be in both. The topics are the
 * tags from the database, by name.
 * Used by the topic pop-up and the profile page.
 */
export function TopicPreferencesEditor({
  value,
  onChange,
}: {
  value: TopicLists
  onChange: (next: TopicLists) => void
}) {
  const { t } = useStrings()
  const { status, tags, retry } = useTags()
  const names = tags.map((tag) => tag.name)

  const toggle = (list: List, tag: string) => {
    const current = value[list]
    const next = current.includes(tag)
      ? current.filter((item) => item !== tag)
      : [...current, tag]
    onChange({ ...value, [list]: next })
  }

  if (status === 'loading')
    return <p role="status">{t.topicPrefs.tagsLoading}</p>
  if (status === 'error') {
    return (
      <p role="alert">
        {t.topicPrefs.tagsFailed}{' '}
        <button type="button" className={styles.retry} onClick={retry}>
          {t.topicPrefs.retry}
        </button>
      </p>
    )
  }

  return (
    <div className={styles.editor}>
      <TopicGroup
        list="liked"
        Icon={ThumbsUp}
        names={names}
        value={value}
        onToggle={toggle}
      />
      <TopicGroup
        list="disliked"
        Icon={ThumbsDown}
        names={names}
        value={value}
        onToggle={toggle}
      />
    </div>
  )
}

type GroupProps = {
  list: List
  Icon: LucideIcon
  names: string[]
  value: TopicLists
  onToggle: (list: List, tag: string) => void
}

function TopicGroup({ list, Icon, names, value, onToggle }: GroupProps) {
  const { t } = useStrings()
  const hintId = useId()
  const other: List = list === 'liked' ? 'disliked' : 'liked'
  const takenText =
    list === 'liked' ? t.topicPrefs.inDisliked : t.topicPrefs.inLiked

  return (
    <fieldset
      className={styles.group}
      data-list={list}
      aria-describedby={hintId}
    >
      <legend className={styles.legend}>
        <Icon size={18} aria-hidden="true" />
        {t.topicPrefs[list]}
      </legend>
      <p id={hintId} className={styles.hint}>
        {list === 'liked' ? t.topicPrefs.likedHint : t.topicPrefs.dislikedHint}
      </p>
      <div className={styles.chips}>
        {names.map((tag) => {
          const checked = value[list].includes(tag)
          const taken = value[other].includes(tag)
          const TagIcon = tagIcon(tag)
          return (
            <label key={tag} className={styles.chip}>
              <input
                type="checkbox"
                checked={checked}
                disabled={taken}
                onChange={() => onToggle(list, tag)}
              />
              {checked ? (
                <Check size={16} aria-hidden="true" />
              ) : (
                <TagIcon size={16} aria-hidden="true" />
              )}
              {tagLabel(tag, t)}
              {taken && <span className="sr-only"> {takenText}</span>}
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
