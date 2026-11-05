/*
 * Ask Nova – MOCK version.
 * There is no AI behind this yet. Answers are built from the story data
 * after a short delay, so the UI can be designed and tested.
 * Swap the body of `askNova` for a real API call later; the UI only
 * depends on the `NovaAnswer` shape.
 */
import type { Story } from '../types'

export type NovaAnswer = {
  text: string
  sources: string[]
  uncertainty: string
}

export const SUGGESTED_QUESTIONS = [
  'Explain it simpler',
  'What led to this?',
  'What happens next?',
] as const

const FAKE_DELAY_MS = 900

function firstSentence(text: string) {
  return text.split(/(?<=\.)\s/)[0]
}

function lastSentence(text: string) {
  const sentences = text.split(/(?<=\.)\s/)
  return sentences[sentences.length - 1]
}

export async function askNova(story: Story, question: string): Promise<NovaAnswer> {
  await new Promise((resolve) => setTimeout(resolve, FAKE_DELAY_MS))

  const q = question.toLowerCase()
  const { why } = story
  // Stories from the API have no analysis yet; fall back to the article text.
  const firstPoint = why?.points[0]?.text ?? story.content?.[1] ?? ''
  const background = why?.background ?? story.content?.[2] ?? firstSentence(story.summary)
  let text: string

  if (q.includes('simple')) {
    text = `In short: ${firstSentence(story.summary)} ${firstPoint}`
  } else if (q.includes('led to') || q.includes('why')) {
    text = `Some background: ${background} That is part of why this is news now.`
  } else if (q.includes('next')) {
    text = `Nothing is final yet. Based on the reporting so far: ${lastSentence(story.summary)}`
  } else if (q.includes('for me')) {
    text = `${story.whyPicked} The most direct effect: ${firstPoint}`
  } else if (why) {
    text = `Here is what the sources agree on: ${why.points.map((point) => `${point.keyword} – ${point.text}`).join(' ')}`
  } else {
    text = `Here is what the article says: ${story.summary}`
  }

  return {
    text,
    sources: [story.publisher.name, ...story.readMore.perspectives.map((p) => p.publisher)],
    uncertainty: story.aiNote.uncertainty,
  }
}
