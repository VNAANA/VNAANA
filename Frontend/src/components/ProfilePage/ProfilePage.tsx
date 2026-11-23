import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import {
  readGoogleStatus,
  readPasswordStatus,
  setAccountPassword,
} from '../../utils/accountAuth'
import { supabase } from '../../utils/supabase'
import { startGoogleLink, type LinkResult } from '../../utils/googleLink'
import {
  ArrowLeft,
  ChevronDown,
  CircleCheck,
  KeyRound,
  LogOut,
} from 'lucide-react'
import type { useAuth } from '../../hooks/useAuth'
import { useStrings } from '../../hooks/useStrings'
import { getAccount } from '../../utils/account'
import { setLanguage } from '../../utils/language'
import type { Language } from '../../utils/language'
import { useTopicPreferences } from '../../hooks/useTopicPreferences'
import { setTopicPreferences } from '../../utils/topicPreferences'
import { PROFILE_TABS, profileHash } from '../../utils/profileTabs'
import type { ProfileTab } from '../../utils/profileTabs'
import { AccountAvatar } from '../AccountAvatar/AccountAvatar'
import { TopicPreferencesEditor } from '../TopicPreferences/TopicPreferencesEditor'
import type { TopicLists } from '../TopicPreferences/TopicPreferencesEditor'
import { Logo } from '../Navigation/Logo'
import { MobileTabBar } from '../Navigation/MobileBars'
import styles from './ProfilePage.module.css'

function PasswordForm({
  userId,
  enabled,
  onSaved,
}: {
  userId: string
  enabled: boolean
  onSaved: () => void
}) {
  const { t } = useStrings()
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [current, setCurrent] = useState('')
  const [saving, setSaving] = useState(false)
  const [nonce, setNonce] = useState<string | null>(null)
  const [result, setResult] = useState<
    'failed' | 'weak' | 'mismatch' | 'incorrect' | null
  >(null)

  async function save(event: FormEvent) {
    event.preventDefault()
    if (saving) return
    if (password !== confirmation) {
      setResult('mismatch')
      return
    }
    setSaving(true)
    setResult(null)
    try {
      const { error } = await setAccountPassword(
        userId,
        password,
        nonce?.trim(),
        enabled ? current : undefined,
      )
      if (error) {
        if (error.code === 'reauthentication_needed' && nonce === null) {
          const challenge = await supabase.auth.reauthenticate()
          if (challenge.error) setResult('failed')
          else setNonce('')
        } else {
          if (error.code === 'weak_password') setResult('weak')
          else if (error.code === 'invalid_credentials') setResult('incorrect')
          else setResult('failed')
        }
      } else {
        setPassword('')
        setCurrent('')
        setConfirmation('')
        setNonce(null)
        onSaved()
      }
    } catch {
      setResult('failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={styles.passwordForm} onSubmit={save}>
      {enabled && (
        <label>
          {t.profile.currentPassword}
          <input
            className={styles.select}
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
          />
        </label>
      )}
      <label className={styles.sectionTitle} htmlFor="account-password">
        {t.profile.newPassword}
      </label>
      <input
        id="account-password"
        className={styles.select}
        type="password"
        autoComplete="new-password"
        required
        minLength={8}
        value={password}
        onChange={(event) => {
          setPassword(event.target.value)
          setResult(null)
        }}
      />
      <label>
        {t.profile.confirmPassword}
        <input
          className={styles.select}
          type="password"
          autoComplete="new-password"
          required
          value={confirmation}
          aria-invalid={result === 'mismatch' || undefined}
          onChange={(event) => {
            setConfirmation(event.target.value)
            setResult(null)
          }}
        />
      </label>
      {nonce !== null && (
        <label>
          {t.profile.verificationCode}
          <input
            className={styles.select}
            autoComplete="one-time-code"
            value={nonce}
            required
            onChange={(event) => setNonce(event.target.value)}
          />
        </label>
      )}
      <button className={styles.savePassword} type="submit" disabled={saving}>
        {t.profile.setPassword}
      </button>
      <p className={styles.hint} role="status">
        {result === 'weak'
          ? t.login.notices.weakPassword
          : result && t.profile.passwordResult[result]}
      </p>
    </form>
  )
}

function AuthenticationMethods({
  userId,
  token,
  linkResult,
}: {
  userId: string
  token: string
  linkResult: LinkResult | null
}) {
  const { t } = useStrings()
  const [status, setStatus] = useState<
    'checking' | Awaited<ReturnType<typeof readGoogleStatus>>
  >('checking')
  const [attempt, setAttempt] = useState(0)
  const [linking, setLinking] = useState(false)
  const [message, setMessage] = useState<LinkResult | null>(null)
  const [enabled, setEnabled] = useState<boolean | null>(null)
  const [passwordError, setPasswordError] = useState(false)
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    setPasswordError(false)
    void readPasswordStatus(token, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setEnabled(value)
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setEnabled(null)
          setPasswordError(true)
        }
      })
    return () => controller.abort()
  }, [token, attempt])

  useEffect(() => {
    let active = true
    setStatus('checking')
    void readGoogleStatus(userId).then((value) => {
      if (active) setStatus(value)
    })
    return () => {
      active = false
    }
  }, [userId, attempt, linkResult])

  async function connectGoogle() {
    setLinking(true)
    setMessage(null)
    const result = await startGoogleLink(userId)
    if (result) {
      setMessage(result)
      setLinking(false)
      setAttempt((previous) => previous + 1)
    }
  }

  return (
    <section className={styles.actions} aria-labelledby="auth-methods-heading">
      <h2 id="auth-methods-heading" className={styles.sectionTitle}>
        {t.profile.authMethods}
      </h2>
      <p
        role="status"
        className={status === 'connected' ? styles.verified : undefined}
      >
        {status === 'connected' && <CircleCheck size={16} aria-hidden="true" />}
        {t.profile.googleStatus[status]}
      </p>
      {status === 'disconnected' && (
        <button
          type="button"
          className={styles.signOut}
          disabled={linking}
          onClick={connectGoogle}
        >
          {t.profile.connectGoogle}
        </button>
      )}
      {(status === 'unavailable' || passwordError) && (
        <button
          type="button"
          className={styles.signOut}
          onClick={() => setAttempt((previous) => previous + 1)}
        >
          {t.profile.retryMethods}
        </button>
      )}
      {message && <p role="status">{t.profile.linkResult[message]}</p>}
      {enabled === true && (
        <p className={styles.verified}>
          <CircleCheck size={16} aria-hidden="true" />
          {t.profile.passwordEnabled}
        </p>
      )}
      {passwordError && <p role="status">{t.profile.passwordUnavailable}</p>}
      {enabled !== null && (
        <details
          className={styles.passwordPanel}
          onChange={() => setSaved(false)}
        >
          <summary className={styles.passwordToggle}>
            <KeyRound size={20} aria-hidden="true" />
            <span>
              <strong>
                {enabled ? t.profile.changePassword : t.profile.addPassword}
              </strong>
              <span className={styles.passwordHint}>
                {t.profile.passwordHint}
              </span>
            </span>
            <ChevronDown
              size={18}
              className={styles.chevron}
              aria-hidden="true"
            />
          </summary>
          <PasswordForm
            userId={userId}
            enabled={enabled}
            onSaved={() => {
              setEnabled(true)
              setSaved(true)
            }}
          />
        </details>
      )}
      <div role="status" aria-live="polite">
        {saved && (
          <p className={styles.verified}>
            <CircleCheck size={16} aria-hidden="true" />
            {t.profile.passwordResult.saved}
          </p>
        )}
      </div>
    </section>
  )
}

type Props = {
  auth: ReturnType<typeof useAuth>
  /** The open tab, read from the URL hash by App. */
  tab: ProfileTab
}

/*
 * The signed-in user's profile, split into tabs along the top:
 * "Profile settings" (name, email, language, authentication methods, sign out) and "Topics".
 */
export function ProfilePage({ auth, tab }: Props) {
  const {
    session,
    checkingSession,
    backendStatus,
    signingOut,
    signOut,
    linkResult,
  } = auth
  const { language, t } = useStrings()
  const { preferences, userId } = useTopicPreferences()
  const [topicsFailed, setTopicsFailed] = useState(false)
  const [languageFailed, setLanguageFailed] = useState(false)

  const changeLanguage = (next: Language) => {
    setLanguageFailed(false)
    setLanguage(next).catch(() => setLanguageFailed(true))
  }

  const changeTopics = (next: TopicLists) => {
    setTopicsFailed(false)
    setTopicPreferences(next).catch(() => setTopicsFailed(true))
  }
  const account = getAccount(session)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const tabRefs = useRef<Partial<Record<ProfileTab, HTMLButtonElement | null>>>(
    {},
  )

  // Coming from the feed, start keyboard and screen reader users at the page title
  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  // replace() so switching tabs doesn't fill the back button's history.
  const openTab = (next: ProfileTab) =>
    window.location.replace(profileHash(next))

  // Tabs pattern: arrow keys, Home and End move between tabs and open them.
  const onTabKeyDown = (event: KeyboardEvent) => {
    const index = PROFILE_TABS.indexOf(tab)
    const last = PROFILE_TABS.length - 1
    const target = {
      ArrowRight: index === last ? 0 : index + 1,
      ArrowLeft: index === 0 ? last : index - 1,
      Home: 0,
      End: last,
    }[event.key]
    if (target === undefined) return
    event.preventDefault()
    const next = PROFILE_TABS[target]
    openTab(next)
    tabRefs.current[next]?.focus()
  }

  return (
    <div className={styles.page}>
      <header className={styles.top}>
        <Logo />
        <a href="#" className={styles.back}>
          <ArrowLeft size={18} aria-hidden="true" />
          {t.common.backToFeed}
        </a>
      </header>

      <main className={styles.main}>
        <div className={styles.card}>
          <h1 ref={headingRef} className={styles.title} tabIndex={-1}>
            {t.profile.title}
          </h1>

          {account ? (
            <>
              <div
                role="tablist"
                aria-label={t.profile.tabs.label}
                className={styles.tabs}
              >
                {PROFILE_TABS.map((id) => (
                  <button
                    key={id}
                    ref={(element) => {
                      tabRefs.current[id] = element
                    }}
                    type="button"
                    role="tab"
                    id={`profile-tab-${id}`}
                    aria-controls={`profile-panel-${id}`}
                    aria-selected={id === tab}
                    tabIndex={id === tab ? 0 : -1}
                    className={styles.tab}
                    onClick={() => openTab(id)}
                    onKeyDown={onTabKeyDown}
                  >
                    {t.profile.tabs[id]}
                  </button>
                ))}
              </div>

              <div
                role="tabpanel"
                id={`profile-panel-${tab}`}
                aria-labelledby={`profile-tab-${tab}`}
                className={styles.panel}
              >
                {tab === 'settings' && (
                  <>
                    <div className={styles.identity}>
                      <AccountAvatar account={account} size={64} />
                      <div className={styles.who}>
                        <p className={styles.name}>{account.name}</p>
                        {account.email && (
                          <p className={styles.email}>{account.email}</p>
                        )}
                      </div>
                    </div>

                    <section
                      className={styles.actions}
                      aria-labelledby="language-heading"
                    >
                      <h2 id="language-heading" className={styles.sectionTitle}>
                        {t.profile.language}
                      </h2>
                      <select
                        className={styles.select}
                        value={language}
                        onChange={(event) =>
                          changeLanguage(event.target.value as Language)
                        }
                        aria-labelledby="language-heading"
                        aria-describedby="language-hint"
                      >
                        {/* Each language is named in itself, so it can be found whatever is selected */}
                        <option value="en" lang="en">
                          English
                        </option>
                        <option value="nl" lang="nl">
                          Nederlands
                        </option>
                      </select>
                      <p id="language-hint" className={styles.hint}>
                        {t.profile.languageHint}
                      </p>
                      <p className={styles.topicsError} role="alert">
                        {languageFailed && t.profile.languageSaveFailed}
                      </p>
                    </section>

                    {session && (
                      <AuthenticationMethods
                        key={session.user.id}
                        userId={session.user.id}
                        token={session.access_token}
                        linkResult={linkResult}
                      />
                    )}

                    <section
                      className={styles.actions}
                      aria-labelledby="account-actions-heading"
                    >
                      <h2
                        id="account-actions-heading"
                        className={styles.sectionTitle}
                      >
                        {t.profile.accountActions}
                      </h2>
                      <button
                        type="button"
                        className={styles.signOut}
                        onClick={signOut}
                        disabled={signingOut}
                      >
                        <LogOut size={20} aria-hidden="true" />
                        {signingOut ? t.common.signingOut : t.common.signOut}
                      </button>
                    </section>
                  </>
                )}

                {tab === 'topics' && (
                  <section
                    className={styles.actions}
                    aria-labelledby="topics-heading"
                  >
                    <h2 id="topics-heading" className={styles.sectionTitle}>
                      {t.nav.topics}
                    </h2>
                    {userId ? (
                      <>
                        <p className={styles.hint}>
                          {t.topicPrefs.profileHint}
                        </p>
                        <TopicPreferencesEditor
                          value={preferences}
                          onChange={changeTopics}
                        />
                        <p className={styles.topicsError} role="alert">
                          {topicsFailed && t.topicPrefs.saveFailed}
                        </p>
                      </>
                    ) : (
                      <p className={styles.hint}>{t.common.checkingSession}</p>
                    )}
                  </section>
                )}
              </div>
            </>
          ) : (
            <p className={styles.intro}>
              {checkingSession ? (
                t.common.checkingSession
              ) : (
                <>
                  {t.profile.notLoggedIn.before}
                  <a href="#login">{t.profile.notLoggedIn.link}</a>
                  {t.profile.notLoggedIn.after}
                </>
              )}
            </p>
          )}

          <p className={styles.notice} role="status">
            {linkResult && t.profile.linkResult[linkResult]}
            {backendStatus && t.auth[backendStatus]}
          </p>
        </div>
      </main>

      {/* Phones keep the bottom tab bar here too; on desktop it hides itself. */}
      <div className={styles.tabBar}>
        <MobileTabBar
          account={account}
          checkingSession={checkingSession}
          current="profile"
        />
      </div>
    </div>
  )
}
