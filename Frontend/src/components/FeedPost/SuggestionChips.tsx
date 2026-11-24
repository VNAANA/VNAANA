import { useStrings } from '../../hooks/useStrings'
import { NOVA_SUGGESTIONS } from '../../utils/nova'
import styles from './SuggestionChips.module.css'

/*
 * Quick questions for Nova, in the display language. Each one is sent as a
 * normal question, "Explain it simpler" too.
 * "row" keeps them on one line that scrolls sideways.
 */
export function SuggestionChips({
  onPick,
  tone = 'wrap',
  disabled = false,
}: {
  onPick: (question: string) => void
  tone?: 'wrap' | 'row'
  disabled?: boolean
}) {
  const { language, t } = useStrings()

  return (
    <ul
      className={`${styles.chips} ${styles[tone]}`}
      aria-label={t.nova.suggestions}
    >
      {NOVA_SUGGESTIONS[language].map((question) => (
        <li key={question}>
          <button
            type="button"
            className={styles.chip}
            onClick={() => onPick(question)}
            disabled={disabled}
          >
            {question}
          </button>
        </li>
      ))}
    </ul>
  )
}
