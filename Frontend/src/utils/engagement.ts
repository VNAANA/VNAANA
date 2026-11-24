/*
 * What the signed-in user does with stories, stored on the backend as
 * engagement events (POST /users/{id}/events) so the For You ranking can
 * learn from it (Backend/Logic/Algorithm/scoring.py). Nothing goes into
 * story_reactions.
 *
 * - reactions: like (+2 for the story's tags) and dislike (−5). "Not
 *              interested" is a dislike; tapping again sends reaction_removed.
 *              Only a story's latest one counts (Algorithm/reactions.py).
 *              GET /users/{id}/reactions gives back the current ones, worked
 *              out from those events.
 * - share (+5) when a share or link copy succeeds, and
 *   read_complete (+1) once the reader moves past a post's first part.
 *
 * Only for a signed-in user with analytics consent (the backend refuses
 * anything else). Signed out, nothing is stored and the buttons aren't offered.
 */
import { apiUrl } from './api'
import { readStorage, writeStorage } from './storage'
import { supabase } from './supabase'
import { readTopicState, subscribeTopicState } from './topicPreferences'

export type Reaction = 'like' | 'dislike'
export type EventType = 'share' | 'read_complete'
type ReactionEvent = Reaction | 'reaction_removed'

// ---------- Who may be tracked ----------

/* The backend user ID when reactions and events may be stored, else null. */
function trackedUser() {
  const { userId, analyticsConsent } = readTopicState()
  return userId && analyticsConsent ? userId : null
}

async function call(method: string, path: string, body?: unknown) {
  const token = (await supabase.auth.getSession()).data.session?.access_token
  if (!token) throw new Error('Not signed in')
  const response = await fetch(apiUrl(path), {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) throw new Error(`Request failed: ${method} ${path}`)
  return response.status === 204 ? null : response.json()
}

// ---------- Reactions ----------

/*
 * `shown` is what the buttons show (changed straight away when tapped);
 * `stored` is what the backend has. A save always sends the newest shown
 * value, one at a time per story, so quick taps can't arrive out of order.
 * If a save fails, the button goes back to the stored value.
 */
let shown = new Map<string, Reaction>()
let stored = new Map<string, Reaction>()
let loadedFor: string | null = null
const saving = new Map<string, Promise<void>>()
const listeners = new Set<() => void>()

function notify() {
  listeners.forEach((listener) => listener())
}

export function subscribeReactions(listener: () => void) {
  listeners.add(listener)
  syncUser()
  return () => {
    listeners.delete(listener)
  }
}

export function readReaction(storyId: string): Reaction | null {
  return shown.get(storyId) ?? null
}

/* Load the user's reactions when they sign in; forget them when they sign out or switch accounts. */
function syncUser() {
  const userId = trackedUser()
  if (userId === loadedFor) return
  loadedFor = userId
  shown = new Map()
  stored = new Map()
  saving.clear()
  notify()
  if (!userId) return
  call('GET', `/users/${userId}/reactions`)
    .then((rows: { story_id: string; reaction: Reaction }[]) => {
      if (loadedFor !== userId) return
      stored = new Map(rows.map((row) => [row.story_id, row.reaction]))
      // Keep anything tapped while this was loading.
      shown = new Map([...stored, ...shown])
      notify()
    })
    .catch(() => {
      // The buttons still work; they just start empty.
    })
}

subscribeTopicState(syncUser)

/* Show the new reaction now (null removes it), then store it. Resolves false if it couldn't be stored. */
export function setReaction(
  storyId: string,
  reaction: Reaction | null,
): Promise<boolean> {
  const userId = trackedUser()
  if (!userId) return Promise.resolve(false)
  if (reaction) shown.set(storyId, reaction)
  else shown.delete(storyId)
  notify()

  const run = (saving.get(storyId) ?? Promise.resolve()).then(async () => {
    if (loadedFor !== userId) return
    const want = shown.get(storyId) ?? null
    if (want === (stored.get(storyId) ?? null)) return
    await sendEvent(userId, storyId, want ?? 'reaction_removed')
    if (loadedFor !== userId) return
    if (want) stored.set(storyId, want)
    else stored.delete(storyId)
  })
  const settled = run.then(
    () => true,
    () => {
      // Back to what the backend has.
      if (loadedFor === userId) {
        const kept = stored.get(storyId)
        if (kept) shown.set(storyId, kept)
        else shown.delete(storyId)
        notify()
      }
      return false
    },
  )
  saving.set(
    storyId,
    settled.then(() => {}),
  )
  return settled
}

// ---------- Events ----------

const SESSION_KEY = 'vnaana.sessionId'

/* One ID per browser tab session; the backend groups events by it. */
export function sessionId() {
  let id = readStorage(SESSION_KEY, 'session')
  if (!id) {
    id = crypto.randomUUID()
    writeStorage(SESSION_KEY, id, 'session')
  }
  return id
}

// A story counts as read once per page load, so going back and forth doesn't add up.
const readStories = new Set<string>()

function sendEvent(
  userId: string,
  storyId: string,
  eventType: EventType | ReactionEvent,
  metadata?: Record<string, unknown>,
) {
  return call('POST', `/users/${userId}/events`, {
    session_id: sessionId(),
    story_id: storyId,
    event_type: eventType,
    occurred_at: new Date().toISOString(),
    ...(metadata ? { metadata } : {}),
  })
}

/* Send one event. Never throws: tracking must not break reading or sharing. */
export async function logEvent(
  storyId: string,
  eventType: EventType,
  metadata?: Record<string, unknown>,
) {
  const userId = trackedUser()
  if (!userId) return false
  try {
    await sendEvent(userId, storyId, eventType, metadata)
    return true
  } catch {
    return false
  }
}

/*
 * The reader moved past the post's first part. Sent once per story per page load.
 * If sending fails (e.g. the backend doesn't know the event type yet), the next swipe tries again.
 */
export function logReadComplete(storyId: string, part: number, parts: number) {
  if (readStories.has(storyId) || !trackedUser()) return
  readStories.add(storyId)
  void logEvent(storyId, 'read_complete', { part, parts }).then((sent) => {
    if (!sent) readStories.delete(storyId)
  })
}
