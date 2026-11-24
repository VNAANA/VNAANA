/*
 * Ask Nova for a story: POST /ai/stories/{id}/ask (see Backend/ASK_NOVA_API.md).
 * The backend reads the story's linked articles itself, so the frontend only
 * sends the question, the answer language and the recent conversation.
 */
import type { NovaErrorCode } from '../data/strings'
import { apiUrl } from './api'
import type { Language } from './language'

/* Nova answers in the display language chosen on the profile page. */
export type NovaLanguage = Language

/* Limits the backend enforces (HTTP 422 otherwise). */
export const MAX_NOVA_QUESTION_CHARS = 500
const MAX_HISTORY_EXCHANGES = 2
const MAX_HISTORY_MESSAGE_CHARS = 500
const MAX_HISTORY_BYTES = 2_000

/* A failed request. The chat shows the message for `code` in the display language. */
export class NovaError extends Error {
  readonly code: NovaErrorCode

  constructor(code: NovaErrorCode) {
    super(`Nova request failed: ${code}`)
    this.code = code
  }
}

export type NovaAnswer = {
  text: string
  /** URLs of the linked articles Nova cited, checked by the backend. */
  sources: string[]
  uncertainty: string
  status: 'answered' | 'insufficient_information'
}

/* One finished question and answer, used as context for follow-up questions. */
export type NovaExchange = { question: string; answer: string }

type HistoryMessage = { role: 'user' | 'assistant'; content: string }

// Shown in the answer language; the label is also the question sent to Nova.
export const NOVA_SUGGESTIONS: Record<NovaLanguage, readonly string[]> = {
  en: ['Explain it simpler', 'What led to this?', 'What happens next?'],
  nl: ['Leg het eenvoudiger uit', 'Wat leidde hiertoe?', 'Wat gebeurt er nu?'],
}

export async function askNova(
  storyId: string,
  question: string,
  language: NovaLanguage,
  exchanges: readonly NovaExchange[] = [],
): Promise<NovaAnswer> {
  const url = apiUrl(`/ai/stories/${encodeURIComponent(storyId)}/ask`)
  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        language,
        history: toHistory(exchanges),
      }),
    })
  } catch {
    throw new NovaError('unreachable')
  }
  if (response.status === 404) throw new NovaError('notFound')
  if (response.status === 422) throw new NovaError('invalidRequest')
  if (response.status === 503) throw new NovaError('modelUnavailable')
  if (!response.ok) throw new NovaError('failed')

  let answer: unknown
  try {
    answer = await response.json()
  } catch {
    throw new NovaError('invalidResponse')
  }
  if (
    !answer ||
    typeof answer !== 'object' ||
    !('text' in answer) ||
    typeof answer.text !== 'string' ||
    !('sources' in answer) ||
    !Array.isArray(answer.sources) ||
    !answer.sources.every((source: unknown) => typeof source === 'string') ||
    !('uncertainty' in answer) ||
    typeof answer.uncertainty !== 'string' ||
    !('status' in answer) ||
    (answer.status !== 'answered' &&
      answer.status !== 'insufficient_information')
  ) {
    throw new NovaError('invalidResponse')
  }
  return answer as NovaAnswer
}

/*
 * The history the backend accepts: at most the last two exchanges, oldest
 * first, each message at most 500 characters, and at most 2,000 UTF-8 bytes
 * in total. Older exchanges are dropped until it fits.
 */
export function toHistory(
  exchanges: readonly NovaExchange[],
): HistoryMessage[] {
  // Blank messages are rejected, so an exchange with one is left out.
  const complete = exchanges.filter(
    (exchange) => exchange.question.trim() && exchange.answer.trim(),
  )
  const history = complete
    .slice(-MAX_HISTORY_EXCHANGES)
    .flatMap((exchange): HistoryMessage[] => [
      { role: 'user', content: clip(exchange.question) },
      { role: 'assistant', content: clip(exchange.answer) },
    ])
  while (history.length > 0 && historyBytes(history) > MAX_HISTORY_BYTES)
    history.splice(0, 2)
  return history
}

function clip(text: string): string {
  const trimmed = text.trim()
  return trimmed.length <= MAX_HISTORY_MESSAGE_CHARS
    ? trimmed
    : `${trimmed.slice(0, MAX_HISTORY_MESSAGE_CHARS - 1).trimEnd()}…`
}

// The backend measures Python's json.dumps output, which puts a space after
// every ':' and ','. Counting those spaces keeps this a safe upper bound.
function historyBytes(history: HistoryMessage[]): number {
  const json = JSON.stringify(history)
  const separators = history.length * 3 + Math.max(0, history.length - 1)
  return new TextEncoder().encode(json).length + separators
}
