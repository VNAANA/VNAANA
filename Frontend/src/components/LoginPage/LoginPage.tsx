import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowLeft, Eye, EyeOff } from 'lucide-react'
import { Logo } from '../Navigation/Logo'
import styles from './LoginPage.module.css'
import { supabase } from '../../utils/supabase'
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

/* Google's "G", as used on "Continue with Google" buttons */
function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  )
}

/*
 * Google sign-in uses Supabase and initializes the verified backend profile.
 * Email/password login remains a design preview.
 */
export function LoginPage({ auth }: { auth: ReturnType<typeof useAuth> }) {
  const { session, checkingSession, backendStatus, signingOut, signOut: onSignOut } = auth
  const { t } = useStrings()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<Errors>({})
  const [notice, setNotice] = useState<LoginNotice | null>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const emailRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)
  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    const found = validate(email, password)
    setErrors(found)
    if (found.email) emailRef.current?.focus()
    else if (found.password) passwordRef.current?.focus()
    else setNotice('notConnected')
  }

  const onGoogle = async () => {
    setNotice('openingGoogle')

    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/`,
        },
      })

      if (error) throw error
    } catch {
      setNotice('googleFailed')
    }
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
