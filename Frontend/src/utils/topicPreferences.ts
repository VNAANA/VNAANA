/*
 * The user's liked and disliked topics, and whether to show the topic pop-up.
 * Kept in this browser until the backend can store them. A topic is never in
 * both lists: setTopicPreferences() removes overlap, preferring "liked".
 */
import { TAG_NAMES } from '../data/tags'
import type { TagName } from '../data/tags'
import { readStorage, removeStorage, writeStorage } from './storage'

export type TopicPreferences = {
  liked: TagName[]
  disliked: TagName[]
  /** True once the user saved or skipped the pop-up, so it isn't shown again. */
  asked: boolean
}

type State = { preferences: TopicPreferences; promptRequested: boolean }

const PREFERENCES_KEY = 'vnaana.topicPreferences'
// Session storage: set by a successful login, cleared when the pop-up closes.
const PROMPT_KEY = 'vnaana.topicPromptRequested'

const listeners = new Set<() => void>()
let state: State = {
  preferences: parse(readStorage(PREFERENCES_KEY)),
  promptRequested: readStorage(PROMPT_KEY, 'session') === 'true',
}

export function readTopicState(): State {
  return state
}

export function subscribeTopicState(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function setTopicPreferences(next: TopicPreferences) {
  const liked = clean(next.liked)
  const disliked = clean(next.disliked).filter((tag) => !liked.includes(tag))
  const preferences = { liked, disliked, asked: next.asked }
  writeStorage(PREFERENCES_KEY, JSON.stringify(preferences))
  update({ ...state, preferences })
}

/* Ask for topics on the next main page (after logging in). */
export function requestTopicPrompt() {
  writeStorage(PROMPT_KEY, 'true', 'session')
  update({ ...state, promptRequested: true })
}

/* The pop-up was saved or skipped: don't ask again. */
export function closeTopicPrompt() {
  removeStorage(PROMPT_KEY, 'session')
  setTopicPreferences({ ...state.preferences, asked: true })
  update({ ...state, promptRequested: false })
}

function update(next: State) {
  state = next
  listeners.forEach((listener) => listener())
}

/* Known tags only, no duplicates, in the default tag order. */
function clean(tags: unknown): TagName[] {
  if (!Array.isArray(tags)) return []
  return TAG_NAMES.filter((tag) => tags.includes(tag))
}

function parse(raw: string | null): TopicPreferences {
  try {
    const value = raw ? JSON.parse(raw) : {}
    const liked = clean(value.liked)
    return {
      liked,
      disliked: clean(value.disliked).filter((tag) => !liked.includes(tag)),
      asked: value.asked === true,
    }
  } catch {
    return { liked: [], disliked: [], asked: false }
  }
}
