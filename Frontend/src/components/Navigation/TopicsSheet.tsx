import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { useStrings } from '../../hooks/useStrings'
import { TopicLinks } from './TopicLinks'
import styles from './Navigation.module.css'

type Props = {
  /** Shows "Edit": customising topics is only for signed-in users. */
  canEdit: boolean
  onEdit: () => void
  onClose: () => void
}

/*
 * The mobile Topics tab: the sidebar's topic list in a sheet that slides up from the bottom.
 * A native modal <dialog> keeps focus inside and closes on Escape; tapping the dimmed area closes it too.
 */
export function TopicsSheet({ canEdit, onEdit, onClose }: Props) {
  const { t } = useStrings()
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog && !dialog.open) dialog.showModal()
    return () => dialog?.close()
  }, [])

  return (
    <dialog
      ref={dialogRef}
      className={styles.sheet}
      aria-labelledby="topics-sheet-heading"
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      // The dialog has no padding, so a click on the dialog element itself is a click on the backdrop.
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className={styles.sheetBody}>
        <div className={styles.sheetHeader}>
          <h2 id="topics-sheet-heading" className={styles.sheetTitle}>
            {t.nav.topics}
          </h2>
          {canEdit && (
            <button
              type="button"
              className={styles.editLink}
              aria-label={t.nav.editTopics}
              aria-haspopup="dialog"
              onClick={onEdit}
            >
              {t.nav.edit}
            </button>
          )}
          <button
            type="button"
            className={styles.sheetClose}
            aria-label={t.nav.closeTopics}
            onClick={onClose}
          >
            <X size={20} aria-hidden="true" />
          </button>
        </div>
        <TopicLinks onNavigate={onClose} />
      </div>
    </dialog>
  )
}
