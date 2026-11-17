import { useEffect, useRef, useState } from 'react'
import { useStrings } from '../../hooks/useStrings'
import { agreeToConsent } from '../../utils/topicPreferences'
import styles from './ConsentDialog.module.css'

/*
 * Shown after login while the profile has no analytics consent, e.g. a new
 * account made with Google, which skips the registration form. Consent is
 * required, so the pop-up has a single "I understand" button and can't be
 * closed with Escape. The topic pop-up comes after it.
 */
export function ConsentDialog() {
  const { t } = useStrings()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog && !dialog.open) dialog.showModal()
    return () => dialog?.close()
  }, [])

  const accept = async () => {
    if (busy) return
    setBusy(true)
    setFailed(false)
    try {
      // On success the profile has consent and App replaces this pop-up with the topic pop-up.
      await agreeToConsent()
    } catch {
      setFailed(true)
      setBusy(false)
    }
  }

  return (
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      aria-labelledby="consent-dialog-title"
      aria-describedby="consent-dialog-text"
      aria-busy={busy || undefined}
      // Escape must not dismiss it: consent is required.
      onCancel={(event) => event.preventDefault()}
    >
      <h2 id="consent-dialog-title" className={styles.title}>
        {t.consentPrompt.title}
      </h2>
      <p id="consent-dialog-text" className={styles.intro}>
        {t.consentPrompt.text}
      </p>

      <p className={styles.error} role="alert">
        {failed && t.consentPrompt.saveFailed}
      </p>

      <div className={styles.actions}>
        <button type="button" className={styles.save} onClick={() => void accept()} disabled={busy}>
          {busy ? t.topicPrefs.saving : t.consentPrompt.understand}
        </button>
      </div>
    </dialog>
  )
}
