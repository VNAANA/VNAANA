import type { CSSProperties } from 'react'
import type { Topic } from '../types'

/*
 * A topic's soft background and dark text colour as two CSS variables,
 * --topic-bg and --topic-ink, for a component's styles to read.
 * The colours themselves live in tokens.css. No topic → neutral grey.
 */
export function topicColorStyle(topic?: Topic) {
  const key = topic?.toLowerCase() ?? 'unknown'
  return {
    '--topic-bg': `var(--topic-${key}-bg)`,
    '--topic-ink': `var(--topic-${key}-ink)`,
  } as CSSProperties
}
