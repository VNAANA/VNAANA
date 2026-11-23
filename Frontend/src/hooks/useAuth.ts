import { useEffect, useRef, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import type { AuthStatus } from '../data/strings'
import { supabase } from '../utils/supabase'
import { useHash } from './useHash'
import {
  finishGoogleLink,
  readLinkCallback,
  type LinkResult,
} from '../utils/googleLink'
import { bootstrapProfile, giveAnalyticsConsent } from '../utils/profileApi'
import type { Profile } from '../utils/profileApi'
import { clearTopicState, loadTopicState } from '../utils/topicPreferences'
import { clearProfileLanguage, loadProfileLanguage } from '../utils/language'

const initialUrl = new URL(window.location.href)
const linkCallback = readLinkCallback(initialUrl)
const oauthError =
  initialUrl.searchParams.has('error') ||
  new URLSearchParams(initialUrl.hash.slice(1)).has('error')
/*
 * The registration form's required consent checkbox is kept in Supabase user
 * metadata; copy it to the profile on the first login. Used only while consent
 * was never set, so it can't undo a later choice. Without consent (e.g. a new
 * Google account) App shows the consent pop-up instead. A failure is not
 * fatal: the pop-up asks, or the next bootstrap tries again.
 */
async function applySignUpConsent(
  profile: Profile,
  session: Session,
): Promise<Profile> {
  const agreedAtSignUp =
    session.user.user_metadata?.personalization_consent === true
  if (
    profile.analyticsConsent ||
    !agreedAtSignUp ||
    profile.consentUpdatedAt !== null
  )
    return profile
  try {
    return await giveAnalyticsConsent(profile.id, session.access_token)
  } catch {
    return profile
  }
}

/** Keep authentication alive on both the feed and the login page. */
export function useAuth() {
  const [session, setSession] = useState<Session | null>(null)
  const [checkingSession, setCheckingSession] = useState(true)
  // A message for the user while signing in or out; the page shows it in the display language
  const [backendStatus, setBackendStatus] = useState<AuthStatus | null>(null)
  const [signingOut, setSigningOut] = useState(false)
  const [readyToken, setReadyToken] = useState<string | null>(null)
  const hash = useHash()
  const [linkResult, setLinkResult] = useState<LinkResult | null>(null)
  const [callback, setCallback] = useState(linkCallback)
  const completion = useRef<Promise<LinkResult> | null>(null)
  const loginCallbackHandled = useRef(false)

  useEffect(() => {
    if (checkingSession || linkCallback || loginCallbackHandled.current) return
    loginCallbackHandled.current = true
    if (oauthError || (initialUrl.searchParams.has('code') && !session)) {
      window.history.replaceState(null, '', window.location.pathname + '#login')
      window.dispatchEvent(new Event('hashchange'))
      setBackendStatus('signInFailed')
    }
  }, [checkingSession, session])

  useEffect(() => {
    if (!linkCallback) return
    let active = true
    completion.current ??= finishGoogleLink(linkCallback)
    void completion.current.then((result) => {
      if (!active) return
      setLinkResult(result)
      window.history.replaceState(
        null,
        '',
        window.location.pathname + '#profile',
      )
      window.dispatchEvent(new Event('hashchange'))
    })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (hash === '#login' && session && readyToken === session.access_token) {
      window.location.hash = ''
    }
  }, [hash, session, readyToken])

  useEffect(() => {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, next) => {
      if (event === 'SIGNED_OUT') {
        setCallback(null)
        setLinkResult(null)
      }
      if (event === 'INITIAL_SESSION' && !next) setCallback(null)
      setSession(next)
      setCheckingSession(false)
    })
    return () => subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!session) {
      setReadyToken(null)
      clearTopicState()
      clearProfileLanguage()
      return
    }
    // A stale or mismatched linking callback must never provision another profile.
    if (callback && (!linkResult || session.user.id !== callback.subject))
      return
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 15000)
    let active = true
    const token = session.access_token
    const current = session

    async function bootstrap() {
      // No "in progress" text: this runs on every load with a saved session, so it would flash each time.
      try {
        const profile = await applySignUpConsent(
          await bootstrapProfile(token, controller.signal),
          current,
        )
        if (active) {
          loadTopicState(profile)
          // The registration form keeps its language in Supabase user metadata.
          loadProfileLanguage(
            profile.id,
            profile.language,
            current.user.user_metadata?.language,
          )
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
  }, [session, linkResult, callback])

  async function signOut() {
    setSigningOut(true)
    try {
      const { error } = await supabase.auth.signOut({ scope: 'local' })
      if (error) throw error
      setSession(null)
      setLinkResult(null)
      setBackendStatus(null)
      window.location.hash = ''
    } catch {
      setBackendStatus('signOutFailed')
    } finally {
      setSigningOut(false)
    }
  }

  return {
    session,
    checkingSession,
    backendStatus,
    signingOut,
    signOut,
    linkResult,
  }
}
