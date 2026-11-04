import { useStrings } from '../../hooks/useStrings'
import { NOVA_SUGGESTIONS } from '../../utils/nova'
import type { NovaSuggestion } from '../../utils/nova'
import styles from './SuggestionChips.module.css'

/*
 * Quick questions for Nova, in the display language.
 * "row" keeps them on one line that scrolls sideways.
 */
export function SuggestionChips({ onPick, tone = 'wrap', disabled = false }: { onPick: (suggestion: NovaSuggestion) => void; tone?: 'wrap' | 'row'; disabled?: boolean }) {
  const { language, t } = useStrings()

  return (
    <ul className={`${styles.chips} ${styles[tone]}`} aria-label={t.nova.suggestions}>
      {NOVA_SUGGESTIONS[language].map((suggestion) => (
        <li key={suggestion.label}>
          <button type="button" className={styles.chip} onClick={() => onPick(suggestion)} disabled={disabled}>
            {suggestion.label}
          </button>
        </li>
      ))}
    </ul>
  )
}
