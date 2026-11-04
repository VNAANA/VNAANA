import { useSyncExternalStore } from 'react'
import { STRINGS } from '../data/strings'
import { readLanguage, subscribeLanguage } from '../utils/language'

/* The current display language and its labels. Re-renders when the language changes. */
export function useStrings() {
  const language = useSyncExternalStore(subscribeLanguage, readLanguage, readLanguage)
  return { language, t: STRINGS[language] }
}
