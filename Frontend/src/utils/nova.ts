/* Ask Nova's single article-grounded API request. */
import type { NovaArticle } from '../types'
import type { NovaErrorCode } from '../data/strings'
import { apiUrl } from './api'
import type { Language } from './language'

/* Nova answers in the display language chosen on the profile page. */
export type NovaLanguage = Language
export const MAX_NOVA_ARTICLE_CHARS = 12_000

/* A failed request. The chat shows the message for `code` in the display language. */
export class NovaError extends Error {
  readonly code: NovaErrorCode

  constructor(code: NovaErrorCode) {
    super(`Nova request failed: ${code}`)
    this.code = code
  }
}

export type NovaSuggestion = {
  label: string
  action: 'ask' | 'simplify'
}

export type NovaAnswer = {
  text: string
  sources: string[]
  uncertainty: string
  status: 'answered' | 'insufficient_information'
}

// Shown in the answer language; the label is also the question sent to Nova.
export const NOVA_SUGGESTIONS: Record<NovaLanguage, readonly NovaSuggestion[]> = {
  en: [
    { label: 'Explain it simpler', action: 'simplify' },
    { label: 'What led to this?', action: 'ask' },
    { label: 'What happens next?', action: 'ask' },
  ],
  nl: [
    { label: 'Leg het eenvoudiger uit', action: 'simplify' },
    { label: 'Wat leidde hiertoe?', action: 'ask' },
    { label: 'Wat gebeurt er nu?', action: 'ask' },
  ],
}

export async function askNova(article: NovaArticle, question: string, language: NovaLanguage): Promise<NovaAnswer> {
  return requestNova('/ai/ask', {
    article_text: article.groundingText,
    question,
    language,
    ...(article.sourceUrl ? { source_url: article.sourceUrl } : {}),
  })
}

export async function simplifyNova(article: NovaArticle, language: NovaLanguage): Promise<NovaAnswer> {
  return requestNova('/ai/summarize', {
    article_text: article.groundingText,
    language,
    ...(article.sourceUrl ? { source_url: article.sourceUrl } : {}),
  })
}

async function requestNova(path: '/ai/ask' | '/ai/summarize', body: Record<string, unknown>): Promise<NovaAnswer> {
  const url = apiUrl(path)
  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new NovaError('unreachable')
  }
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
    !answer || typeof answer !== 'object' ||
    !('text' in answer) || typeof answer.text !== 'string' ||
    !('sources' in answer) || !Array.isArray(answer.sources) ||
    !answer.sources.every((source: unknown) => typeof source === 'string') ||
    !('uncertainty' in answer) || typeof answer.uncertainty !== 'string' ||
    !('status' in answer) ||
    (answer.status !== 'answered' && answer.status !== 'insufficient_information')
  ) {
    throw new NovaError('invalidResponse')
  }
  return answer as NovaAnswer
}
