import { NOVA_SUGGESTIONS } from '../../utils/nova'
import type { NovaSuggestion } from '../../utils/nova'
import styles from './SuggestionChips.module.css'

/* Quick questions for Nova. "row" keeps them on one line that scrolls sideways. */
export function SuggestionChips({ onPick, tone = 'wrap', disabled = false }: { onPick: (suggestion: NovaSuggestion) => void; tone?: 'wrap' | 'row'; disabled?: boolean }) {
  return (
    <ul className={`${styles.chips} ${styles[tone]}`} aria-label="Suggested questions">
      {NOVA_SUGGESTIONS.map((suggestion) => (
        <li key={suggestion.label}>
          <button type="button" className={styles.chip} onClick={() => onPick(suggestion)} disabled={disabled}>
            {suggestion.label}
          </button>
        </li>
      ))}
    </ul>
  )
}
