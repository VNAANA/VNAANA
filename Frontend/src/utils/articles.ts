/*
 * Articles from the backend, turned into feed stories.
 * The API only has the raw article (title, description, scraped content),
 * so Nova's analysis parts of a Story are left empty or filled with honest defaults.
 */
import type { Strings } from '../data/strings'
import type { Story } from '../types'
import { apiUrl } from './api'

/* The parts of the backend's ArticleRead response that the feed uses. */
export type ApiArticle = {
  id: string
  provider: { name: string; domain: string; reliability_status: string }
  canonical_url: string
  title: string
  description: string | null
  content: string | null
  author: string | null
  published_at: string | null
  first_seen_at: string
}

export const FEED_SIZE = 3

const SUMMARY_MAX_CHARS = 320
const WORDS_PER_MINUTE = 200

export async function fetchRandomStories(signal?: AbortSignal): Promise<Story[]> {
  const response = await fetch(apiUrl(`/articles/random?limit=${FEED_SIZE}`), { signal })
  if (!response.ok) throw new Error('Articles request failed')
  const articles: ApiArticle[] = await response.json()
  return articles.map(articleToStory)
}

export function articleToStory(article: ApiArticle): Story {
  const content = toParagraphs(article.content)
  const description = htmlToText(article.description)
  const summary = shorten(description || content[0] || '')
  const hasFullArticle = !!article.content?.trim()
  const previewText = [article.title.trim(), description].filter(Boolean).join('\n\n')
  const groundingText = hasFullArticle ? article.content! : previewText

  return {
    id: article.id,
    // Keep AI grounding separate from the shortened text used by the feed display.
    ...(groundingText ? {
      novaArticle: {
        groundingText,
        groundingMode: hasFullArticle ? 'full_article' : 'preview',
        ...(!hasFullArticle ? { previewIncludesDescription: !!description } : {}),
        ...(article.canonical_url?.trim() ? { sourceUrl: article.canonical_url } : {}),
      },
    } : {}),
    publisher: {
      name: article.provider.name,
      initials: initials(article.provider.name),
      verified: article.provider.reliability_status === 'verified',
    },
    author: article.author ?? undefined,
    publishedAt: new Date(article.published_at ?? article.first_seen_at),
    feedReason: 'forYou',
    whyPicked: 'Picked at random from the latest articles while your personal feed is being built.',
    title: article.title,
    summary,
    content: content.length > 0 ? content : undefined,
    aiNote: { sourceCount: 1 },
    readMore: {
      url: article.canonical_url,
      readMinutes: readMinutes(article.content),
      perspectives: [],
    },
  }
}

/* RSS descriptions often contain HTML. DOMParser never runs scripts, so this is safe. */
function htmlToText(html: string | null) {
  if (!html) return ''
  const text = new DOMParser().parseFromString(html, 'text/html').body.textContent ?? ''
  return text.replace(/\s+/g, ' ').trim()
}

/* Cut long text at the last full sentence that fits. */
function shorten(text: string, max = SUMMARY_MAX_CHARS) {
  if (text.length <= max) return text
  const cut = text.slice(0, max)
  const sentenceEnd = cut.lastIndexOf('. ')
  return sentenceEnd > max / 2 ? cut.slice(0, sentenceEnd + 1) : `${cut.slice(0, cut.lastIndexOf(' '))}…`
}

/* Scraped content split into paragraphs. The "- Name, reporter" byline lines at the top are skipped. */
function toParagraphs(content: string | null) {
  return (content ?? '')
    .split(/\n+/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith('- '))
}

function initials(name: string) {
  const words = name.split(/\s+/).filter(Boolean)
  if (words.length === 1) return words[0].length <= 3 ? words[0].toUpperCase() : words[0].slice(0, 2).toUpperCase()
  return words
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
    .toUpperCase()
}

function readMinutes(content: string | null) {
  if (!content) return undefined
  const words = content.split(/\s+/).filter(Boolean).length
  return Math.max(1, Math.round(words / WORDS_PER_MINUTE))
}

/* "2h ago" in the display language; older than a week becomes a date. */
export function timeAgo(date: Date, t: Strings) {
  const minutes = Math.round((Date.now() - date.getTime()) / 60000)
  if (minutes < 1) return t.post.timeAgo.justNow
  if (minutes < 60) return t.post.timeAgo.minutes(minutes)
  const hours = Math.round(minutes / 60)
  if (hours < 24) return t.post.timeAgo.hours(hours)
  const days = Math.round(hours / 24)
  if (days < 7) return t.post.timeAgo.days(days)
  return date.toLocaleDateString(t.locale, { day: 'numeric', month: 'short' })
}
