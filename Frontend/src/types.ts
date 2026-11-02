export type Topic =
  | 'Technology'
  | 'Sports'
  | 'Politics'
  | 'Entertainment'
  | 'Science'
  | 'World'
  | 'Business'

export type FeedReason = 'forYou' | 'dontMiss'

export type NovaArticle = {
  groundingText: string
  groundingMode: 'full_article' | 'preview'
  previewIncludesDescription?: boolean
  sourceUrl?: string
}

/*
 * Articles from the API don't have a topic, image or Nova's "why it matters"
 * analysis yet, so those are optional and the post shows a fallback instead.
 */
export type Story = {
  id: string
  novaArticle?: NovaArticle
  publisher: { name: string; initials: string; verified: boolean }
  author?: string
  publishedAgo: string // "2h ago"
  topic?: Topic
  location?: string // "Eindhoven"
  feedReason: FeedReason
  whyPicked: string
  image?: { src: string; alt: string }
  title: string
  summary: string
  /** The scraped article text, one string per paragraph. Adds a "Full article" part. */
  content?: string[]
  why?: { heading: string; points: { keyword: string; text: string }[]; background: string }
  aiNote: { sourceCount: number; uncertainty: string }
  readMore: {
    url: string
    readTime?: string
    perspectives: { publisher: string; angle: string; url: string }[]
  }
}

export type User = {
  firstName: string
  name: string
  username: string
  initials: string
  followedTopics: Topic[]
}
