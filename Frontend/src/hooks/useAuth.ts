import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import type { AuthStatus } from '../data/strings'
import { apiUrl } from '../utils/api'
import { supabase } from '../utils/supabase'
import { useHash } from './useHash'

/** Keep authentication alive on both the feed and the login page. */
export function useAuth() {
  const [session, setSession] = useState<Session | null>(null)
  const [checkingSession, setCheckingSession] = useState(true)
  // A message for the user while signing in or out; the page shows it in the display language
  const [backendStatus, setBackendStatus] = useState<AuthStatus | null>(null)
  const [signingOut, setSigningOut] = useState(false)
  const [readyToken, setReadyToken] = useState<string | null>(null)
  const hash = useHash()

  useEffect(() => {
    if (hash === '#login' && session && readyToken === session.access_token) {
      window.location.hash = ''
    }
  }, [hash, session, readyToken])

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next)
      setCheckingSession(false)
    })
    return () => subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!session) {
      setBackendStatus(null)
      setReadyToken(null)
      return
    }
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 15000)
    let active = true
    const token = session.access_token

    async function bootstrap() {
      setBackendStatus('finishingSignIn')
      try {
        const response = await fetch(apiUrl('/users/me/bootstrap'), {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        })
        if (!response.ok) throw new Error('Profile request failed')
        const profile = await response.json()
        if (typeof profile.id !== 'string') throw new Error('Invalid profile')
        if (active) {
          setBackendStatus(null)
          setReadyToken(token)
          if (window.location.hash === '#login') window.location.hash = ''
          // The SDK has exchanged the OAuth code before emitting the session.
          const url = new URL(window.location.href)
          if (url.searchParams.has('code')) {
            url.searchParams.delete('code')
            window.history.replaceState(null, '', url)
          }
        }
      } catch {
        if (active) setBackendStatus('signInFailed')
      } finally {
        window.clearTimeout(timeout)
      }
    }
    void bootstrap()
    return () => {
      active = false
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [session])

  async function signOut() {
    setSigningOut(true)
    try {
      const { error } = await supabase.auth.signOut({ scope: 'local' })
      if (error) throw error
      setSession(null)
      setBackendStatus(null)
      window.location.hash = ''
    } catch {
      setBackendStatus('signOutFailed')
    } finally {
      setSigningOut(false)
    }
  }

  return { session, checkingSession, backendStatus, signingOut, signOut }
}
