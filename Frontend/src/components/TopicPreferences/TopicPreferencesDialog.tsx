import { useEffect, useRef, useState } from 'react'
import { useStrings } from '../../hooks/useStrings'
import { closeTopicPrompt, readTopicState, setTopicPreferences } from '../../utils/topicPreferences'
import { TopicPreferencesEditor } from './TopicPreferencesEditor'
import type { TopicLists } from './TopicPreferencesEditor'
import styles from './TopicPreferences.module.css'

/*
 * The pop-up shown after logging in: asks which topics the user likes and dislikes.
 * A native modal <dialog> keeps focus inside and closes on Escape (same as "Skip").
 */
export function TopicPreferencesDialog() {
  const { t } = useStrings()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [draft, setDraft] = useState<TopicLists>(() => {
    const { liked, disliked } = readTopicState().preferences
    return { liked, disliked }
  })

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog && !dialog.open) dialog.showModal()
    return () => dialog?.close()
  }, [])

  const save = () => {
    setTopicPreferences({ ...draft, asked: true })
    closeTopicPrompt()
  }

  return (
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      aria-labelledby="topic-dialog-title"
      aria-describedby="topic-dialog-intro"
      onCancel={closeTopicPrompt}
    >
      <h2 id="topic-dialog-title" className={styles.title}>
        {t.topicPrefs.title}
      </h2>
      <p id="topic-dialog-intro" className={styles.intro}>
        {t.topicPrefs.intro}
      </p>

      <TopicPreferencesEditor value={draft} onChange={setDraft} />

      <div className={styles.actions}>
        <button type="button" className={styles.skip} onClick={closeTopicPrompt}>
          {t.topicPrefs.skip}
        </button>
        <button type="button" className={styles.save} onClick={save}>
          {t.topicPrefs.save}
        </button>
      </div>
    </dialog>
  )
}
