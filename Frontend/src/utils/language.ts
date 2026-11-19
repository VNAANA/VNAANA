/*
 * The display language. It sets every label in the app and the language Nova
 * answers in. For a signed-in user it is stored on the backend profile
 * (users.language) and loaded by useAuth; nothing is kept in the browser.
 * Signed out, it starts from the browser's language and lasts until reload.
 */
import { saveLanguage } from './profileApi'
import { removeStorage } from './storage'

export type Language = 'en' | 'nl'

export function isLanguage(value: unknown): value is Language {
  return value === 'en' || value === 'nl'
}

// The language used to be stored in this browser; drop that copy.
removeStorage('vnaana.language')

const listeners = new Set<() => void>()
let current: Language = browserLanguage()
// Backend profile to save changes to; null while signed out.
let profileId: string | null = null
setDocumentLanguage(current)

function browserLanguage(): Language {
  const preferred = typeof navigator === 'undefined' ? '' : navigator.language
  return preferred.toLowerCase().startsWith('nl') ? 'nl' : 'en'
}

export function readLanguage(): Language {
  return current
}

function apply(language: Language) {
  if (language === current) return
  current = language
  setDocumentLanguage(language)
  listeners.forEach((listener) => listener())
}

// Saves run one at a time and always send the newest choice.
let saving: Promise<void> = Promise.resolve()

function persist(): Promise<void> {
  const userId = profileId
  if (!userId) return Promise.resolve()
  const run = saving.catch(() => {}).then(() => {
    if (profileId !== userId) return
    return saveLanguage(userId, current)
  })
  saving = run
  return run
}

/** Change the language now; when signed in, also save it to the profile. Rejects if that save failed. */
export function setLanguage(language: Language): Promise<void> {
  apply(language)
  return persist()
}

/*
 * Called by useAuth once the backend profile is loaded. A profile without a
 * language yet (a new account) gets the one chosen at registration, or the
 * one currently shown.
 */
export function loadProfileLanguage(userId: string, saved: Language | null, chosenAtSignUp: unknown) {
  profileId = userId
  if (saved) {
    apply(saved)
    return
  }
  apply(isLanguage(chosenAtSignUp) ? chosenAtSignUp : current)
  void persist().catch(() => {})
}

/** Called by useAuth on sign-out: keep showing the current language, stop saving it. */
export function clearProfileLanguage() {
  profileId = null
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
