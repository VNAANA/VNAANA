import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Info, SendHorizontal } from 'lucide-react'
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

  return (
    <div className={styles.log} role="log" aria-live="polite" aria-label="Conversation with Nova">
      {chat.groundingMode === 'preview' && (
        <p className={styles.intro}>
          {chat.previewIncludesDescription
            ? 'Full article text is unavailable. Nova is using only the headline and available description.'
            : 'Full article text is unavailable. Nova is using only the headline.'}
        </p>
      )}
      {chat.messages.length === 0 && (
        <p className={styles.intro}>
          {chat.tooLong
            ? 'Ask Nova is unavailable: this article exceeds the 12,000-character AI limit.'
            : chat.available
              ? chat.groundingMode === 'full_article'
                ? 'Nova answers using only this original article, not other sources or previous messages.'
                : 'Questions are answered only when the available preview supports them.'
              : 'Ask Nova is unavailable because the original article text is missing.'}
        </p>
      )}
      {chat.messages.map((message) =>
        message.from === 'user' ? (
          <p key={message.id} className={styles.user}>
            <span className="sr-only">You asked: </span>
            {message.text}
          </p>
        ) : 'error' in message ? (
          <p key={message.id} className={styles.nova}>
            {message.error}
          </p>
        ) : (
          <div key={message.id} className={styles.nova}>
            <span className="sr-only">Nova replied: </span>
            {message.answer.status === 'insufficient_information' && <strong>Not answered from this article</strong>}
            <p>{message.answer.text}</p>
            {message.answer.sources.length > 0 && <p className={styles.sources}>
              <strong>Submitted article URL:</strong> {message.answer.sources.join(', ')}
            </p>}
            <p className={styles.uncertain}>
              <Info size={14} aria-hidden="true" />
              <span>
                <strong>Not certain:</strong> {message.answer.uncertainty}
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
          Nova is checking the article…
        </p>
      )}
    </div>
  )
}

export function NovaComposer() {
  const { story, chat, composerFocusRequest } = usePost()
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
        <label className={styles.language}>
          Answer language
          <select value={chat.language} onChange={(event) => chat.setLanguage(event.target.value as 'en' | 'nl')} aria-label="Nova answer language">
            <option value="en">English</option>
            <option value="nl">Dutch</option>
          </select>
        </label>
        <label htmlFor={inputId} className="sr-only">
          Ask Nova about this story
        </label>
        <input
          ref={inputRef}
          id={inputId}
          className={styles.input}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask Nova anything…"
          autoComplete="off"
          disabled={!chat.available || chat.pending}
        />
        <button type="submit" className={styles.send} aria-label="Send question to Nova" disabled={!chat.available || chat.pending}>
          <SendHorizontal size={18} aria-hidden="true" />
        </button>
      </form>
    </div>
  )
}
