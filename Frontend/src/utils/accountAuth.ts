import { supabase } from './supabase'
import { apiUrl } from './api'

type Registration = {
  email: string
  password: string
  firstName: string
  lastName: string
  language: string
  consent: boolean
}

export function registerWithPassword(form: Registration) {
  const given = form.firstName.trim()
  const family = form.lastName.trim()
  return supabase.auth.signUp({
    email: form.email.trim(),
    password: form.password,
    options: {
      emailRedirectTo: window.location.origin + '/',
      data: {
        given_name: given, family_name: family, full_name: given + ' ' + family,
        language: form.language, personalization_consent: form.consent,
      },
    },
  })
}

export function loginWithPassword(email: string, password: string) {
  return supabase.auth.signInWithPassword({ email: email.trim(), password })
}

/** Google identities are visible in the verified user. Password credentials are private. */
export async function readGoogleStatus(expectedId: string): Promise<'connected' | 'disconnected' | 'unavailable'> {
  try {
    const { data, error } = await supabase.auth.getUser()
    if (error || data.user?.id !== expectedId || !Array.isArray(data.user.identities)) {
      return 'unavailable'
    }
    return data.user.identities.some(identity => identity.provider === 'google') ? 'connected' : 'disconnected'
  } catch {
    return 'unavailable'
  }
}

export async function readPasswordStatus(token: string, signal: AbortSignal): Promise<boolean> {
  const response = await fetch(apiUrl('/auth/me/password-status'), {
    headers: { Authorization: 'Bearer ' + token }, cache: 'no-store', signal,
  })
  if (!response.ok) throw new Error('Password status unavailable')
  const status = await response.json()
  if (typeof status.enabled !== 'boolean') throw new Error('Invalid password status')
  return status.enabled
}

export async function setAccountPassword(expectedId: string, password: string, nonce?: string, currentPassword?: string) {
  const { data, error } = await supabase.auth.getUser()
  if (error || data.user?.id !== expectedId) throw new Error('Session changed')
  return supabase.auth.updateUser({
    password,
    ...(nonce && { nonce }),
    ...(currentPassword && { current_password: currentPassword }),
  })
}
