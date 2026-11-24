import { flushSync } from 'react-dom'

// How long a transition may wait for the new screen to be ready (e.g. an image to decode).
const MAX_WAIT_MS = 250

/*
 * Runs a React state update as a View Transition when the browser supports it
 * and the user hasn't asked for reduced motion; otherwise it just runs it.
 * The update is flushed synchronously when it runs. Without a transition that is
 * right away; with one, the browser runs it a frame later, after its "before" picture,
 * so wait for `transition.finished` (or `updateCallbackDone`) before touching the new DOM.
 *
 * `ready` may return a promise for something the new screen needs before the
 * browser takes its "after" picture, so it doesn't animate a half-finished screen.
 * It is never waited on for longer than MAX_WAIT_MS.
 *
 * Returns the transition, or null when there was none.
 */
export function withViewTransition(update: () => void, ready?: () => Promise<unknown>): ViewTransition | null {
  if (!canMorph()) {
    flushSync(update)
    return null
  }
  return document.startViewTransition(async () => {
    flushSync(update)
    if (ready) await Promise.race([ready().catch(() => {}), wait(MAX_WAIT_MS)])
  })
}

/* True when withViewTransition will animate. */
export function canMorph() {
  return typeof document.startViewTransition === 'function' &&
    !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/* Resolves once every image inside `element` can be drawn (broken images count as done). */
export function imagesDecoded(element: Element | null | undefined) {
  const images = element ? [...element.querySelectorAll('img')] : []
  return Promise.all(images.map((image) => image.decode().catch(() => {})))
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
