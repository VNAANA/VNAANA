import { useEffect, useRef, useState } from 'react'
import { useStrings } from '../../hooks/useStrings'
import { finishOnboarding, readTopicState, setTopicPreferences } from '../../utils/topicPreferences'
import { TopicPreferencesEditor } from './TopicPreferencesEditor'
import type { TopicLists } from './TopicPreferencesEditor'
import styles from './TopicPreferences.module.css'

type Props = {
  /**
   * "prompt": shown while the profile's onboarding is not completed. Save and
   *   "Skip for now" both complete onboarding; the pop-up then closes by itself.
   * "edit": opened from the sidebar's Edit link ("Cancel" just closes it).
   */
  mode?: 'prompt' | 'edit'
  /** Called after a successful Save, or Cancel/Escape in edit mode. */
  onClose?: () => void
}

/*
 * Pop-up that asks which topics the user likes and dislikes. Liked topics are
 * saved with PUT /users/{id}/tags, both lists with PUT /users/{id}/preferences.
 * A native modal <dialog> keeps focus inside and closes on Escape (same as Skip/Cancel).
 */
export function TopicPreferencesDialog({ mode = 'prompt', onClose = () => {} }: Props) {
  const { t } = useStrings()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [draft, setDraft] = useState<TopicLists>(() => readTopicState().preferences)
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog && !dialog.open) dialog.showModal()
    return () => dialog?.close()
  }, [])

  const run = async (action: () => Promise<void>) => {
    if (busy) return
    setBusy(true)
    setFailed(false)
    try {
      await action()
      onClose()
    } catch {
      setFailed(true)
      setBusy(false)
    }
  }

  const save = () =>
    run(async () => {
      await setTopicPreferences(draft)
      if (mode === 'prompt') await finishOnboarding()
    })

  // Skipping the first-time prompt still completes onboarding, so it isn't asked again.
  const dismiss = () => (mode === 'prompt' ? run(finishOnboarding) : onClose())

  return (
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      aria-labelledby="topic-dialog-title"
      aria-describedby="topic-dialog-intro"
      aria-busy={busy || undefined}
      onCancel={(event) => {
        // Let React unmount the dialog instead of the browser closing it underneath us.
        event.preventDefault()
        void dismiss()
      }}
    >
      <h2 id="topic-dialog-title" className={styles.title}>
        {t.topicPrefs.title}
      </h2>
      <p id="topic-dialog-intro" className={styles.intro}>
        {t.topicPrefs.intro}
      </p>

      <TopicPreferencesEditor value={draft} onChange={setDraft} />

      <p className={styles.error} role="alert">
        {failed && t.topicPrefs.saveFailed}
      </p>

      <div className={styles.actions}>
        <button type="button" className={styles.skip} onClick={() => void dismiss()} disabled={busy}>
          {mode === 'edit' ? t.topicPrefs.cancel : t.topicPrefs.skip}
        </button>
        <button type="button" className={styles.save} onClick={() => void save()} disabled={busy}>
          {busy ? t.topicPrefs.saving : t.topicPrefs.save}
        </button>
      </div>
    </dialog>
  )
}
