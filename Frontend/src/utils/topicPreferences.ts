/*
 * The signed-in user's consent, liked and disliked topics and onboarding state,
 * loaded from the backend profile by useAuth. Nothing is kept in the browser,
 * so another account on the same browser never sees these topics.
 */
import {
  cleanTopics,
  completeOnboarding,
  giveAnalyticsConsent,
  saveTopics,
} from './profileApi'
import type { Profile, TopicLists } from './profileApi'
import { removeStorage } from './storage'

export type { TopicLists }

type State = {
  preferences: TopicLists
  /** Backend profile ID; null while signed out or before the profile has loaded. */
  userId: string | null
  /** False until the user agreed in the registration form or the consent pop-up. Required to use the app. */
  analyticsConsent: boolean
  /** False until the user saved or skipped the topic pop-up. */
  onboardingCompleted: boolean
}

const EMPTY: State = {
  preferences: { liked: [], disliked: [] },
  userId: null,
  analyticsConsent: false,
  onboardingCompleted: false,
}

// Topics used to be stored in this browser; drop that copy so it can't leak to another account.
removeStorage('vnaana.topicPreferences')
removeStorage('vnaana.topicPromptRequested', 'session')

const listeners = new Set<() => void>()
let state: State = EMPTY

export function readTopicState(): State {
  return state
}

export function subscribeTopicState(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function update(next: State) {
  state = next
  listeners.forEach((listener) => listener())
}

/** Called by useAuth once the backend profile is loaded. */
export function loadTopicState(profile: Profile) {
  update({
    preferences: profile.preferences,
    userId: profile.id,
    analyticsConsent: profile.analyticsConsent,
    onboardingCompleted: profile.onboardingCompleted,
  })
}

/** The consent pop-up: the user ticked the box. */
export async function agreeToConsent(): Promise<void> {
  const userId = state.userId
  if (!userId) throw new Error('Not signed in')
  await giveAnalyticsConsent(userId)
  if (state.userId === userId) update({ ...state, analyticsConsent: true })
}

/** Called by useAuth when the user signs out. */
export function clearTopicState() {
  if (state !== EMPTY) update(EMPTY)
}

// Saves run one at a time and always send the newest lists, so a slow
// response can never overwrite a later change.
let saving: Promise<void> = Promise.resolve()

/** Show the new lists straight away, then store them. Rejects if the backend refused. */
export function setTopicPreferences(next: TopicLists): Promise<void> {
  const userId = state.userId
  if (!userId) return Promise.reject(new Error('Not signed in'))
  update({ ...state, preferences: cleanTopics(next) })
  const run = saving
    .catch(() => {})
    .then(() => {
      if (state.userId !== userId) return
      return saveTopics(userId, state.preferences)
    })
  saving = run
  return run
}

/** Save or skip in the pop-up: mark onboarding as done so it isn't shown again. */
export async function finishOnboarding(): Promise<void> {
  const userId = state.userId
  if (!userId) throw new Error('Not signed in')
  await completeOnboarding(userId)
  if (state.userId === userId) update({ ...state, onboardingCompleted: true })
}
