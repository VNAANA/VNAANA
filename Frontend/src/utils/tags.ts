/*
 * The news tags from the database (GET /tags), loaded once and shared by the
 * sidebar, the topic editor and the Explore filter. Tags don't change while
 * the app is open; after a failure the next retry() loads them again.
 */
import { apiUrl } from './api'

export type ApiTag = { id: string; name: string }

export type TagsState =
  | { status: 'loading'; tags: [] }
  | { status: 'ready'; tags: ApiTag[] }
  | { status: 'error'; tags: [] }

const LOADING: TagsState = { status: 'loading', tags: [] }

let state: TagsState = LOADING
let request: Promise<ApiTag[]> | null = null
const listeners = new Set<() => void>()

function update(next: TagsState) {
  state = next
  listeners.forEach((listener) => listener())
}

/* All tags, sorted by name. Shared: only the first call fetches. */
export function loadTags(): Promise<ApiTag[]> {
  request ??= fetch(apiUrl('/tags'))
    .then((response) => {
      if (!response.ok) throw new Error('Could not load tags')
      return response.json() as Promise<unknown>
    })
    .then((raw) => {
      if (!Array.isArray(raw)) throw new Error('Invalid tags')
      const tags = raw
        .filter(
          (tag): tag is ApiTag =>
            typeof tag?.id === 'string' &&
            typeof tag?.name === 'string' &&
            !!tag.name.trim(),
        )
        .sort((a, b) => a.name.localeCompare(b.name))
      update({ status: 'ready', tags })
      return tags
    })
    .catch((error: unknown) => {
      request = null
      update({ status: 'error', tags: [] })
      throw error
    })
  return request
}

export function readTags(): TagsState {
  return state
}

/* Starts loading on the first subscriber, like a fetch on mount. */
export function subscribeTags(listener: () => void) {
  listeners.add(listener)
  if (state.status === 'loading' && !request) loadTags().catch(() => {})
  return () => {
    listeners.delete(listener)
  }
}

export function retryTags() {
  if (request) return
  update(LOADING)
  loadTags().catch(() => {})
}

/*
 * Tags in the order the user cares about: liked first, then the rest,
 * disliked last. Within each group they keep the given order (by name).
 */
export function orderByPreference<T extends { name: string }>(
  tags: readonly T[],
  preferences: { liked: readonly string[]; disliked: readonly string[] },
): T[] {
  const rank = (tag: T) =>
    preferences.liked.includes(tag.name)
      ? 0
      : preferences.disliked.includes(tag.name)
        ? 2
        : 1
  // Array.prototype.sort is stable, so each group stays in name order.
  return [...tags].sort((a, b) => rank(a) - rank(b))
}
