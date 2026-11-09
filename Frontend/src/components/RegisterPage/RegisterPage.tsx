import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowLeft, Check, Eye, EyeOff } from 'lucide-react'
import { Logo } from '../Navigation/Logo'
import { GoogleIcon } from '../LoginPage/GoogleIcon'
import { startGoogleSignIn } from '../../utils/googleSignIn'
import styles from './RegisterPage.module.css'
import type { LoginNotice, RegisterError } from '../../data/strings'
import type { useAuth } from '../../hooks/useAuth'
import { useStrings } from '../../hooks/useStrings'
import { setLanguage } from '../../utils/language'
import type { Language } from '../../utils/language'
import { rememberRegisteredEmail } from '../../utils/registration'

type Field = 'firstName' | 'lastName' | 'email' | 'password' | 'consent'
type TextField = Exclude<Field, 'consent'>
type Errors = Partial<Record<Field, RegisterError>>
type Form = Record<TextField, string> & { consent: boolean }

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const MIN_PASSWORD = 8
// Focus order for the first error, matching the order on screen
const FIELD_ORDER: Field[] = ['firstName', 'lastName', 'email', 'password', 'consent']

function validate(form: Form): Errors {
  const errors: Errors = {}
  if (!form.firstName.trim()) errors.firstName = 'firstNameMissing'
  if (!form.lastName.trim()) errors.lastName = 'lastNameMissing'
  if (!form.email.trim()) errors.email = 'emailMissing'
  else if (!EMAIL_PATTERN.test(form.email.trim())) errors.email = 'emailInvalid'
  if (!form.password) errors.password = 'passwordMissing'
  else if (form.password.length < MIN_PASSWORD) errors.password = 'passwordShort'
  if (!form.consent) errors.consent = 'consentMissing'
  return errors
}

/*
 * Manual sign-up: name, email, password, language and consent.
 * Topics are chosen after the first login, in the topic pop-up.
 * The backend isn't connected yet: a valid form goes straight to the login page.
 * The language choice applies straight away, like on the profile page.
 */
export function RegisterPage({ auth }: { auth: ReturnType<typeof useAuth> }) {
  const { checkingSession } = auth
  const { language, t } = useStrings()
  const [form, setForm] = useState<Form>({ firstName: '', lastName: '', email: '', password: '', consent: false })
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<Errors>({})
  const [notice, setNotice] = useState<LoginNotice | null>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const fieldRefs = useRef<Partial<Record<Field, HTMLInputElement | null>>>({})

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  const update = (field: TextField, value: string) => setForm((current) => ({ ...current, [field]: value }))

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    const found = validate(form)
    setErrors(found)
    const first = FIELD_ORDER.find((field) => found[field])
    if (first) {
      fieldRefs.current[first]?.focus()
      return
    }
    // TODO backend: POST the account here, then redirect. Payload:
    // { firstName, lastName, email, password, language, consent: true }
    rememberRegisteredEmail(form.email.trim())
    window.location.hash = '#login'
  }

  const onGoogle = async () => {
    setNotice('openingGoogle')
    if (!(await startGoogleSignIn())) setNotice('googleFailed')
  }

  const setRef = (field: Field) => (element: HTMLInputElement | null) => {
    fieldRefs.current[field] = element
  }

  const describedBy = (field: Field, hint?: string) =>
    [hint, errors[field] && `register-${field}-error`].filter(Boolean).join(' ') || undefined

  const errorText = (field: Field) => {
    const error = errors[field]
    return (
      error && (
        <p id={`register-${field}-error`} className={styles.error}>
          {t.register.errors[error]}
        </p>
      )
    )
  }

  const textField = (field: Exclude<TextField, 'password'>, label: string, autoComplete: string, type = 'text') => (
    <div className={styles.field}>
      <label htmlFor={`register-${field}`} className={styles.label}>
        {label}
      </label>
      <input
        ref={setRef(field)}
        id={`register-${field}`}
        className={styles.input}
        type={type}
        autoComplete={autoComplete}
        inputMode={type === 'email' ? 'email' : undefined}
        value={form[field]}
        onChange={(event) => update(field, event.target.value)}
        aria-invalid={errors[field] ? true : undefined}
        aria-describedby={describedBy(field)}
      />
      {errorText(field)}
    </div>
  )

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
            {t.register.title}
          </h1>
          <p className={styles.intro}>{t.register.intro}</p>

          <form className={styles.form} onSubmit={onSubmit} noValidate>
            <div className={styles.nameRow}>
              {textField('firstName', t.register.firstName, 'given-name')}
              {textField('lastName', t.register.lastName, 'family-name')}
            </div>

            {textField('email', t.register.email, 'email', 'email')}

            <div className={styles.field}>
              <label htmlFor="register-password" className={styles.label}>
                {t.register.password}
              </label>
              <div className={styles.passwordWrap}>
                <input
                  ref={setRef('password')}
                  id="register-password"
                  className={styles.input}
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  minLength={MIN_PASSWORD}
                  value={form.password}
                  onChange={(event) => update('password', event.target.value)}
                  aria-invalid={errors.password ? true : undefined}
                  aria-describedby={describedBy('password', 'register-password-hint')}
                />
                <button
                  type="button"
                  className={styles.reveal}
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? t.login.hidePassword : t.login.showPassword}
                  aria-pressed={showPassword}
                >
                  {showPassword ? <Eye size={20} aria-hidden="true" /> : <EyeOff size={20} aria-hidden="true" />}
                </button>
              </div>
              <p id="register-password-hint" className={styles.hint}>
                {t.register.passwordHint}
              </p>
              {errorText('password')}
            </div>

            <div className={styles.field}>
              <label htmlFor="register-language" className={styles.label}>
                {t.register.language}
              </label>
              <select
                id="register-language"
                className={styles.select}
                value={language}
                onChange={(event) => setLanguage(event.target.value as Language)}
                aria-describedby="register-language-hint"
              >
                {/* Each language is named in itself, so it can be found whatever is selected */}
                <option value="en" lang="en">English</option>
                <option value="nl" lang="nl">Nederlands</option>
              </select>
              <p id="register-language-hint" className={styles.hint}>
                {t.register.languageHint}
              </p>
            </div>

            <div className={styles.field}>
              <label className={styles.consent}>
                <input
                  ref={setRef('consent')}
                  type="checkbox"
                  checked={form.consent}
                  onChange={(event) => setForm((current) => ({ ...current, consent: event.target.checked }))}
                  aria-invalid={errors.consent ? true : undefined}
                  aria-describedby={describedBy('consent')}
                />
                <span className={styles.box} aria-hidden="true">
                  {form.consent && <Check size={16} />}
                </span>
                <span>{t.register.consent}</span>
              </label>
              {errorText('consent')}
            </div>

            <button type="submit" className={styles.submit}>
              {t.register.submit}
            </button>
          </form>

          <p className={styles.divider}>
            <span>{t.login.or}</span>
          </p>

          <button type="button" className={styles.google} onClick={onGoogle} disabled={checkingSession}>
            <GoogleIcon />
            {t.register.signUpWithGoogle}
          </button>

          <p className={styles.notice} role="status">
            {notice && t.login.notices[notice]}
          </p>

          <p className={styles.signUp}>
            {t.register.haveAccount}{' '}
            <a href="#login" className={styles.smallLink}>
              {t.common.logIn}
            </a>
          </p>
        </div>
      </main>
    </div>
  )
}
