import { useCallback, useEffect, useState } from 'react'
import type { Article } from '../types'
import { fetchRandomArticles } from '../utils/articles'

type FeedStatus = 'loading' | 'ready' | 'error'

/* Loads the articles for the feed from the backend. `reload` fetches a new set. */
export function useFeedArticles() {
  const [articles, setArticles] = useState<Article[]>([])
  const [status, setStatus] = useState<FeedStatus>('loading')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setStatus('loading')
    fetchRandomArticles(controller.signal)
      .then((next) => {
        setArticles(next)
        setStatus('ready')
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus('error')
      })
    return () => controller.abort()
  }, [attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  return { articles, status, reload }
}
