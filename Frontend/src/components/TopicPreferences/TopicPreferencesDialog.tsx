import { useEffect, useRef, useState } from 'react'
import { useStrings } from '../../hooks/useStrings'
import { closeTopicPrompt, readTopicState, setTopicPreferences } from '../../utils/topicPreferences'
import { TopicPreferencesEditor } from './TopicPreferencesEditor'
import type { TopicLists } from './TopicPreferencesEditor'
import styles from './TopicPreferences.module.css'

type Props = {
  /**
   * "prompt": the pop-up shown once after logging in ("Skip for now" marks it as asked).
   * "edit": opened from the sidebar's Edit link ("Cancel" just closes it).
   */
  mode?: 'prompt' | 'edit'
  /** Called after Save, Cancel/Skip or Escape. Defaults to closing the login prompt. */
  onClose?: () => void
}

/*
 * Pop-up that asks which topics the user likes and dislikes.
 * A native modal <dialog> keeps focus inside and closes on Escape (same as Skip/Cancel).
 */
export function TopicPreferencesDialog({ mode = 'prompt', onClose = closeTopicPrompt }: Props) {
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
    onClose()
  }

  return (
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      aria-labelledby="topic-dialog-title"
      aria-describedby="topic-dialog-intro"
      onCancel={(event) => {
        // Let React unmount the dialog instead of the browser closing it underneath us.
        event.preventDefault()
        onClose()
      }}
    >
      <h2 id="topic-dialog-title" className={styles.title}>
        {t.topicPrefs.title}
      </h2>
      <p id="topic-dialog-intro" className={styles.intro}>
        {t.topicPrefs.intro}
      </p>

      <TopicPreferencesEditor value={draft} onChange={setDraft} />

      <div className={styles.actions}>
        <button type="button" className={styles.skip} onClick={onClose}>
          {mode === 'edit' ? t.topicPrefs.cancel : t.topicPrefs.skip}
        </button>
        <button type="button" className={styles.save} onClick={save}>
          {t.topicPrefs.save}
        </button>
      </div>
    </dialog>
  )
}
