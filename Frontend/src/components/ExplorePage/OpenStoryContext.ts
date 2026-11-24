import { createContext } from 'react'

/*
 * Opens a story from the Explore grid in the reader. The card passes itself
 * so the opening animation can grow the post out of it.
 */
export const OpenStoryContext = createContext<
  (storyId: string, card: HTMLElement) => void
>(() => {})

/* The view-transition-name the card and the post share while one turns into the other. */
export const MORPH_NAME = 'explore-story'
