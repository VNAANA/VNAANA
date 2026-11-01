import { useCallback, useEffect, useState } from 'react'
import type { Story } from '../types'
import { fetchRandomStories } from '../utils/articles'

type FeedStatus = 'loading' | 'ready' | 'error'

/* Loads the stories for the feed from the backend. `reload` fetches a new set. */
export function useFeedStories() {
  const [stories, setStories] = useState<Story[]>([])
  const [status, setStatus] = useState<FeedStatus>('loading')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setStatus('loading')
    fetchRandomStories(controller.signal)
      .then((next) => {
        setStories(next)
        setStatus('ready')
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus('error')
      })
    return () => controller.abort()
  }, [attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  return { stories, status, reload }
}
