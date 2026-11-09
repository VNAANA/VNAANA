import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowLeft, Eye, EyeOff } from 'lucide-react'
import { Logo } from '../Navigation/Logo'
import styles from './LoginPage.module.css'
import { GoogleIcon } from './GoogleIcon'
import { startGoogleSignIn } from '../../utils/googleSignIn'
import { clearRegisteredEmail, readRegisteredEmail } from '../../utils/registration'
import { requestTopicPrompt } from '../../utils/topicPreferences'
import type { LoginError, LoginNotice } from '../../data/strings'
import type { useAuth } from '../../hooks/useAuth'
import { useStrings } from '../../hooks/useStrings'

type Errors = { email?: LoginError; password?: LoginError }

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function validate(email: string, password: string): Errors {
  const errors: Errors = {}
  if (!email.trim()) errors.email = 'emailMissing'
  else if (!EMAIL_PATTERN.test(email.trim())) errors.email = 'emailInvalid'
  if (!password) errors.password = 'passwordMissing'
  return errors
}

/*
 * Google sign-in uses Supabase and initializes the verified backend profile.
 * Email/password login is frontend only: a valid form opens the feed with the topic pop-up.
 */
export function LoginPage({ auth }: { auth: ReturnType<typeof useAuth> }) {
  const { session, checkingSession, backendStatus, signingOut, signOut: onSignOut } = auth
  const { t } = useStrings()
  // Coming from the register page: say the account is ready and fill in its email
  const [registeredEmail] = useState(readRegisteredEmail)
  const [email, setEmail] = useState(registeredEmail ?? '')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<Errors>({})
  const [notice, setNotice] = useState<LoginNotice | null>(registeredEmail ? 'registered' : null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const emailRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    clearRegisteredEmail()
    if (registeredEmail) passwordRef.current?.focus()
  }, [registeredEmail])

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    const found = validate(email, password)
    setErrors(found)
    if (found.email) emailRef.current?.focus()
    else if (found.password) passwordRef.current?.focus()
    else {
      // TODO backend: sign in with email + password here. For now a valid form counts as logged in.
      requestTopicPrompt()
      window.location.hash = ''
    }
  }

  const onGoogle = async () => {
    setNotice('openingGoogle')
    if (!(await startGoogleSignIn())) setNotice('googleFailed')
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
            {t.common.logIn}
          </h1>
          <p className={styles.intro}>{t.login.intro}</p>
            <p className={styles.notice} role="status">
            {checkingSession ? t.common.checkingSession : backendStatus && t.auth[backendStatus]}
          </p>
          <form className={styles.form} onSubmit={onSubmit} noValidate>
            <div className={styles.field}>
              <label htmlFor="login-email" className={styles.label}>
                {t.login.email}
              </label>
              <input
                ref={emailRef}
                id="login-email"
                className={styles.input}
                type="email"
                autoComplete="email"
                inputMode="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                aria-invalid={errors.email ? true : undefined}
                aria-describedby={errors.email ? 'login-email-error' : undefined}
              />
              {errors.email && (
                <p id="login-email-error" className={styles.error}>
                  {t.login.errors[errors.email]}
                </p>
              )}
            </div>

            <div className={styles.field}>
              <div className={styles.labelRow}>
                <label htmlFor="login-password" className={styles.label}>
                  {t.login.password}
                </label>
                <a href="#forgot-password" className={styles.smallLink}>
                  {t.login.forgotPassword}
                </a>
              </div>
              <div className={styles.passwordWrap}>
                <input
                  ref={passwordRef}
                  id="login-password"
                  className={styles.input}
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  aria-invalid={errors.password ? true : undefined}
                  aria-describedby={errors.password ? 'login-password-error' : undefined}
                />
                <button
                  type="button"
                  className={styles.reveal}
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? t.login.hidePassword : t.login.showPassword}
                  aria-pressed={showPassword}
                >
                  {/* The icon shows the current state: crossed-out eye while the password is hidden */}
                  {showPassword ? <Eye size={20} aria-hidden="true" /> : <EyeOff size={20} aria-hidden="true" />}
                </button>
              </div>
              {errors.password && (
                <p id="login-password-error" className={styles.error}>
                  {t.login.errors[errors.password]}
                </p>
              )}
            </div>

            <button type="submit" className={styles.submit}>
              {t.common.logIn}
            </button>
          </form>

          <p className={styles.divider}>
            <span>{t.login.or}</span>
          </p>

          {session ? (
            <button type="button" className={styles.google} onClick={onSignOut} disabled={signingOut}>
              {signingOut ? t.common.signingOut : t.common.signOut}
            </button>
          ) : (
            <button type="button" className={styles.google} onClick={onGoogle} disabled={checkingSession}>
              <GoogleIcon />
              {t.login.continueWithGoogle}
            </button>
          )}

          <p className={styles.notice} role="status">
            {notice && t.login.notices[notice]}
          </p>

          <p className={styles.signUp}>
            {t.login.newHere}{' '}
            <a href="#sign-up" className={styles.smallLink}>
              {t.login.createAccount}
            </a>
          </p>
        </div>
      </main>
    </div>
  )
}
