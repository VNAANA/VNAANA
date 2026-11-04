/*
 * The display language, chosen on the profile page. It sets every label in the
 * app and the language Nova answers in. Remembered until the user clears site data.
 */
import { readStorage, writeStorage } from './storage'

export type Language = 'en' | 'nl'

const LANGUAGE_STORAGE_KEY = 'vnaana.language'

const listeners = new Set<() => void>()
let current: Language = readStorage(LANGUAGE_STORAGE_KEY) === 'nl' ? 'nl' : 'en'
setDocumentLanguage(current)

export function readLanguage(): Language {
  return current
}

export function setLanguage(language: Language) {
  current = language
  writeStorage(LANGUAGE_STORAGE_KEY, language)
  setDocumentLanguage(language)
  listeners.forEach((listener) => listener())
}

/* For useSyncExternalStore: re-render whenever the language changes. */
export function subscribeLanguage(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

// Screen readers pick their pronunciation from <html lang>
function setDocumentLanguage(language: Language) {
  if (typeof document !== 'undefined') document.documentElement.lang = language
}
