import { supabase } from './supabase'
import { readGoogleStatus } from './accountAuth'
import { readStorage, removeStorage, writeStorage } from './storage'

const pendingKey = 'vna.googleLinkSubject'
const flow = 'link-google'
export type LinkResult = 'linked' | 'conflict' | 'disabled' | 'failed'

function failure(code?: string | null): LinkResult {
  if (code === 'identity_already_exists' || code === 'email_exists') return 'conflict'
  return code === 'manual_linking_disabled' ? 'disabled' : 'failed'
}

export async function startGoogleLink(expectedId: string): Promise<LinkResult | null> {
  try {
    const status = await readGoogleStatus(expectedId)
    if (status === 'unavailable') return 'failed'
    if (status === 'connected') return 'linked'
    writeStorage(pendingKey, expectedId, 'session')
    if (readStorage(pendingKey, 'session') !== expectedId) return 'failed'
    const result = await supabase.auth.linkIdentity({
      provider: 'google',
      options: {
        redirectTo: window.location.origin + '/?auth_flow=' + flow,
        queryParams: { prompt: 'select_account' },
      },
    })
    if (!result.error) return null
    removeStorage(pendingKey, 'session')
    return failure(result.error.code)
  } catch {
    removeStorage(pendingKey, 'session')
    return 'failed'
  }
}

// Capture the callback before the SDK finishes processing its PKCE code.
export function readLinkCallback(url: URL) {
  if (url.searchParams.get('auth_flow') !== flow) return null
  const fragment = new URLSearchParams(url.hash.slice(1))
  return {
    subject: readStorage(pendingKey, 'session'),
    error: url.searchParams.get('error_code') || fragment.get('error_code') ||
      url.searchParams.get('error') || fragment.get('error'),
  }
}

export async function finishGoogleLink(callback: NonNullable<ReturnType<typeof readLinkCallback>>): Promise<LinkResult> {
  try {
    // Wait for the shared client's automatic code exchange before reading the user.
    const session = await supabase.auth.getSession()
    if (callback.error) return failure(callback.error)
    if (session.error || !callback.subject || session.data.session?.user.id !== callback.subject) return 'failed'
    return await readGoogleStatus(callback.subject) === 'connected' ? 'linked' : 'failed'
  } catch {
    return 'failed'
  } finally {
    removeStorage(pendingKey, 'session')
  }
}
