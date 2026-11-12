import { useCallback, useEffect, useState } from 'react'
import { fetchExploreArticles } from '../utils/explore'
import type { ExploreFilter, ExploreItem } from '../utils/explore'

type ExploreStatus = 'loading' | 'ready' | 'error'

/* Loads a random set of articles for Explore. `reload` fetches a new set. */
export function useExploreArticles(filter: ExploreFilter) {
  const [items, setItems] = useState<ExploreItem[]>([])
  const [status, setStatus] = useState<ExploreStatus>('loading')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setStatus('loading')
    fetchExploreArticles(filter, controller.signal)
      .then((next) => {
        setItems(next)
        setStatus('ready')
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus('error')
      })
    return () => controller.abort()
  }, [filter, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  return { items, status, reload }
}
