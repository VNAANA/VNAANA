import { useEffect, useRef } from 'react'
import { ArrowLeft, LogOut } from 'lucide-react'
import type { useAuth } from '../../hooks/useAuth'
import { useStrings } from '../../hooks/useStrings'
import { getAccount } from '../../utils/account'
import { setLanguage } from '../../utils/language'
import type { Language } from '../../utils/language'
import { AccountAvatar } from '../AccountAvatar/AccountAvatar'
import { Logo } from '../Navigation/Logo'
import styles from './ProfilePage.module.css'

/* The signed-in user's name and email, the display language, and account actions (for now: sign out). */
export function ProfilePage({ auth }: { auth: ReturnType<typeof useAuth> }) {
  const { session, checkingSession, backendStatus, signingOut, signOut } = auth
  const { language, t } = useStrings()
  const account = getAccount(session)
  const headingRef = useRef<HTMLHeadingElement>(null)

  // Coming from the feed, start keyboard and screen reader users at the page title
  useEffect(() => {
    headingRef.current?.focus()
  }, [])

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
              <div className={styles.identity}>
                <AccountAvatar account={account} size={64} />
                <div className={styles.who}>
                  <p className={styles.name}>{account.name}</p>
                  {account.email && <p className={styles.email}>{account.email}</p>}
                </div>
              </div>

              <section className={styles.actions} aria-labelledby="language-heading">
                <h2 id="language-heading" className={styles.sectionTitle}>
                  {t.profile.language}
                </h2>
                <select
                  className={styles.select}
                  value={language}
                  onChange={(event) => setLanguage(event.target.value as Language)}
                  aria-labelledby="language-heading"
                  aria-describedby="language-hint"
                >
                  {/* Each language is named in itself, so it can be found whatever is selected */}
                  <option value="en" lang="en">English</option>
                  <option value="nl" lang="nl">Nederlands</option>
                </select>
                <p id="language-hint" className={styles.hint}>
                  {t.profile.languageHint}
                </p>
              </section>

              <section className={styles.actions} aria-labelledby="account-actions-heading">
                <h2 id="account-actions-heading" className={styles.sectionTitle}>
                  {t.profile.accountActions}
                </h2>
                <button type="button" className={styles.signOut} onClick={signOut} disabled={signingOut}>
                  <LogOut size={20} aria-hidden="true" />
                  {signingOut ? t.common.signingOut : t.common.signOut}
                </button>
              </section>
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
            {backendStatus && t.auth[backendStatus]}
          </p>
        </div>
      </main>
    </div>
  )
}
