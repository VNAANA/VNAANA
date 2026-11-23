import { useSyncExternalStore } from 'react'
import { readTopicState, subscribeTopicState } from '../utils/topicPreferences'

/* Liked/disliked topics and whether the topic pop-up was requested. Re-renders on change. */
export function useTopicPreferences() {
  return useSyncExternalStore(subscribeTopicState, readTopicState, readTopicState)
}
