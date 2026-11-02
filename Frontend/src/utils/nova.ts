/* Ask Nova's single article-grounded API request. */
import type { NovaArticle } from '../types'
import { apiUrl } from './api'

export type NovaLanguage = 'en' | 'nl'
export const MAX_NOVA_ARTICLE_CHARS = 12_000

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

export const NOVA_SUGGESTIONS: readonly NovaSuggestion[] = [
  { label: 'Explain it simpler', action: 'simplify' },
  { label: 'What led to this?', action: 'ask' },
  { label: 'What happens next?', action: 'ask' },
] as const

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
    throw new Error('Cannot reach the AI service. Check that the backend is running.')
  }
  if (response.status === 422) throw new Error('The article or question is invalid or too long.')
  if (response.status === 503) throw new Error('The AI model is unavailable. Please try again later.')
  if (!response.ok) throw new Error('Nova could not answer right now. Please try again.')

  let answer: unknown
  try {
    answer = await response.json()
  } catch {
    throw new Error('The AI service returned an invalid response.')
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
    throw new Error('The AI service returned an invalid response.')
  }
  return answer as NovaAnswer
}
