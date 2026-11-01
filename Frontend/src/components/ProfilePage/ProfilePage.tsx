import { useEffect, useRef } from 'react'
import { ArrowLeft, LogOut } from 'lucide-react'
import type { useAuth } from '../../hooks/useAuth'
import { getAccount } from '../../utils/account'
import { AccountAvatar } from '../AccountAvatar/AccountAvatar'
import { Logo } from '../Navigation/Logo'
import styles from './ProfilePage.module.css'

/* The signed-in user's name and email, and account actions (for now: sign out). */
export function ProfilePage({ auth }: { auth: ReturnType<typeof useAuth> }) {
  const { session, checkingSession, backendStatus, signingOut, signOut } = auth
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
          Back to feed
        </a>
      </header>

      <main className={styles.main}>
        <div className={styles.card}>
          <h1 ref={headingRef} className={styles.title} tabIndex={-1}>
            Profile
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

              <section className={styles.actions} aria-labelledby="account-actions-heading">
                <h2 id="account-actions-heading" className={styles.sectionTitle}>
                  Account actions
                </h2>
                <button type="button" className={styles.signOut} onClick={signOut} disabled={signingOut}>
                  <LogOut size={20} aria-hidden="true" />
                  {signingOut ? 'Signing out…' : 'Sign out'}
                </button>
              </section>
            </>
          ) : (
            <p className={styles.intro}>
              {checkingSession ? (
                'Checking your session…'
              ) : (
                <>
                  You’re not logged in. <a href="#login">Log in</a> to see your profile.
                </>
              )}
            </p>
          )}

          <p className={styles.notice} role="status">
            {backendStatus}
          </p>
        </div>
      </main>
    </div>
  )
}
