/*
 * Hands the email from the register page to the login page, so login can say
 * "your account is ready" and fill the email in. Session storage, read once.
 */
import { readStorage, removeStorage, writeStorage } from './storage'

const REGISTERED_EMAIL_KEY = 'vnaana.registeredEmail'

export function rememberRegisteredEmail(email: string) {
  writeStorage(REGISTERED_EMAIL_KEY, email, 'session')
}

/* The email of an account just created, or null. */
export function readRegisteredEmail(): string | null {
  return readStorage(REGISTERED_EMAIL_KEY, 'session')
}

/* Call once the login page has shown it, so the notice appears only once. */
export function clearRegisteredEmail() {
  removeStorage(REGISTERED_EMAIL_KEY, 'session')
}
