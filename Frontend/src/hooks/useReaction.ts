import { useCallback, useSyncExternalStore } from 'react'
import { readReaction, subscribeReactions } from '../utils/engagement'

/* The user's like / dislike for one story (null for none). Re-renders when it changes. */
export function useReaction(storyId: string) {
  const read = useCallback(() => readReaction(storyId), [storyId])
  return useSyncExternalStore(subscribeReactions, read, read)
}
