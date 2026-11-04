import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Info, SendHorizontal } from 'lucide-react'
import { useStrings } from '../../hooks/useStrings'
import { usePost } from './PostContext'
import { SuggestionChips } from './SuggestionChips'
import styles from './NovaChat.module.css'

/*
 * Ask Nova inside the post (part 3, "Read more").
 * NovaChatLog shows the conversation; NovaComposer is the chips + input bar
 * pinned to the bottom of the part.
 */

export function NovaChatLog() {
  const { chat } = usePost()
  const { t } = useStrings()

  return (
    <div className={styles.log} role="log" aria-live="polite" aria-label={t.nova.conversation}>
      {chat.groundingMode === 'preview' && (
        <p className={styles.intro}>
          {chat.previewIncludesDescription ? t.nova.previewWithDescription : t.nova.previewHeadlineOnly}
        </p>
      )}
      {chat.messages.length === 0 && (
        <p className={styles.intro}>
          {chat.tooLong
            ? t.nova.tooLong
            : chat.available
              ? chat.groundingMode === 'full_article'
                ? t.nova.fullArticleOnly
                : t.nova.previewOnly
              : t.nova.missingText}
        </p>
      )}
      {chat.messages.map((message) =>
        message.from === 'user' ? (
          <p key={message.id} className={styles.user}>
            <span className="sr-only">{t.nova.youAsked}</span>
            {message.text}
          </p>
        ) : 'error' in message ? (
          <p key={message.id} className={styles.nova}>
            {t.nova.errors[message.error]}
          </p>
        ) : (
          <div key={message.id} className={styles.nova}>
            <span className="sr-only">{t.nova.novaReplied}</span>
            {message.answer.status === 'insufficient_information' && <strong>{t.nova.notAnswered}</strong>}
            <p>{message.answer.text}</p>
            {message.answer.sources.length > 0 && <p className={styles.sources}>
              <strong>{t.nova.submittedUrl}</strong> {message.answer.sources.join(', ')}
            </p>}
            <p className={styles.uncertain}>
              <Info size={14} aria-hidden="true" />
              <span>
                <strong>{t.nova.notCertain}</strong> {message.answer.uncertainty}
              </span>
            </p>
          </div>
        ),
      )}
      {chat.pending && (
        <p className={styles.typing}>
          <span className={styles.typingDots} aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          {t.nova.checking}
        </p>
      )}
    </div>
  )
}

export function NovaComposer() {
  const { story, chat, composerFocusRequest } = usePost()
  const { t } = useStrings()
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const inputId = `${story.id}-nova-input`

  // An Ask Nova button elsewhere in the post asked for the input to be focused.
  // preventScroll stops the browser from scrolling the carousel or the feed.
  useEffect(() => {
    if (composerFocusRequest > 0) inputRef.current?.focus({ preventScroll: true })
  }, [composerFocusRequest])

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    void chat.send(draft)
    setDraft('')
  }

  return (
    <div className={styles.composer}>
      <SuggestionChips onPick={(suggestion) => void chat.sendSuggestion(suggestion)} tone="row" disabled={!chat.available || chat.pending} />
      <form className={styles.form} onSubmit={onSubmit}>
        <label htmlFor={inputId} className="sr-only">
          {t.nova.inputLabel}
        </label>
        <input
          ref={inputRef}
          id={inputId}
          className={styles.input}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={t.nova.placeholder}
          autoComplete="off"
          disabled={!chat.available || chat.pending}
        />
        <button type="submit" className={styles.send} aria-label={t.nova.send} disabled={!chat.available || chat.pending}>
          <SendHorizontal size={18} aria-hidden="true" />
        </button>
      </form>
    </div>
  )
}
