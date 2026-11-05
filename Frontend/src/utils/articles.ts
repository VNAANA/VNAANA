/*
 * Articles from the backend, turned into feed stories.
 * The API only has the raw article (title, description, scraped content),
 * so Nova's analysis parts of a Story are left empty or filled with honest defaults.
 */
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
  const summary = shorten(htmlToText(article.description) || content[0] || '')

  return {
    id: article.id,
    publisher: {
      name: article.provider.name,
      initials: initials(article.provider.name),
      verified: article.provider.reliability_status === 'verified',
    },
    author: article.author ?? undefined,
    publishedAgo: timeAgo(new Date(article.published_at ?? article.first_seen_at)),
    feedReason: 'forYou',
    whyPicked: 'Picked at random from the latest articles while your personal feed is being built.',
    title: article.title,
    summary,
    content: content.length > 0 ? content : undefined,
    aiNote: {
      sourceCount: 1,
      uncertainty: 'Nova hasn’t compared this article with other sources yet.',
    },
    readMore: {
      url: article.canonical_url,
      readTime: readTime(article.content),
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

function readTime(content: string | null) {
  if (!content) return undefined
  const words = content.split(/\s+/).filter(Boolean).length
  return `${Math.max(1, Math.round(words / WORDS_PER_MINUTE))} min read`
}

function timeAgo(date: Date) {
  const minutes = Math.round((Date.now() - date.getTime()) / 60000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}
