import { useTopicPreferences } from './useTopicPreferences'

/*
 * True once a signed-in user's backend profile has loaded. Actions that are
 * stored for the user (like, dislike, not interested, save) need that profile,
 * so they are only offered then. While signed out, or for the moment the
 * profile is still loading, this is false.
 */
export function useSignedIn() {
  return useTopicPreferences().userId !== null
}
