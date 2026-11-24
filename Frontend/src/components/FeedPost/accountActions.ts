export type ActionKind = 'like' | 'dislike' | 'notInterested' | 'share' | 'save'

/* Stored for the user's account, so not offered while signed out. Share works for anyone. */
export const ACCOUNT_ACTIONS: readonly ActionKind[] = [
  'like',
  'dislike',
  'notInterested',
  'save',
]
