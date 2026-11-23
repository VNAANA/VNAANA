export type Topic =
  | 'Technology'
  | 'Sports'
  | 'Politics'
  | 'Entertainment'
  | 'Science'
  | 'World'
  | 'Business'

export type FeedReason = 'forYou' | 'dontMiss'

/* What Ask Nova needs for a post. The backend reads the story's linked articles itself. */
export type NovaStory = {
  storyId: string
  /** Publisher names by article URL, to label the sources Nova cites. */
  sourceLabels: Record<string, string>
}

/*
 * One post in the feed, built from a story (see utils/stories.ts). Stories don't
 * have Nova's "why it matters" analysis yet, and not every story has an image,
 * so those are optional and the post shows a fallback instead.
 */
export type Article = {
  id: string
  /** Missing when the story has no linked articles for Nova to read. */
  novaStory?: NovaStory
  publisher: { name: string; initials: string; verified: boolean }
  author?: string
  publishedAt: Date // shown as "2h ago" in the display language
  topic?: Topic
  /** Tag names from the story, most relevant first. Shown as pills above the post. */
  tags?: string[]
  location?: string // "Eindhoven"
  feedReason: FeedReason
  image?: { src: string; alt: string }
  title: string
  summary: string
  /** The story's context, one string per paragraph. Adds a "Context" part. */
  context?: string[]
  why?: { heading: string; points: { keyword: string; text: string }[]; background: string }
  /** Without an uncertainty, the post says Nova hasn't compared sources yet. */
  aiNote: { sourceCount: number; uncertainty?: string }
  readMore: {
    url: string
    readMinutes?: number
    perspectives: { publisher: string; angle: string; url: string }[]
  }
}
