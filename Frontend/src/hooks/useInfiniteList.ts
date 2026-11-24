import { useCallback, useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

/*
 * One page from the backend. `source` is whatever the loader needs to keep
 * using for later pages (the feed remembers whether it is the personal one).
 * `received` is how many rows the backend returned, so the next offset is
 * right even when duplicates are dropped.
 */
export type Page<T, S> = {
  items: T[]
  received: number
  source: S
  done: boolean
}

export type PageLoader<T, S> = (
  offset: number,
  source: S | null,
  signal: AbortSignal,
) => Promise<Page<T, S>>

type Status = 'loading' | 'ready' | 'error'
type More = 'idle' | 'loading' | 'error' | 'done'

/*
 * A list that loads page by page. The first page loads when `resetKey`
 * changes (and `enabled` is true); `loadMore` appends the next one.
 * Items already in the list are skipped, because the backend order can
 * shift between requests (a story gets updated, the ranking changes).
 */
export function useInfiniteList<T extends { id: string }, S>(
  loadPage: PageLoader<T, S>,
  resetKey: unknown,
  enabled = true,
) {
  const [items, setItems] = useState<T[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [more, setMore] = useState<More>('idle')
  const [attempt, setAttempt] = useState(0)
  const loader = useRef(loadPage)
  const cursor = useRef({
    offset: 0,
    source: null as S | null,
    busy: true,
    done: false,
    ids: new Set<string>(),
  })
  const moreController = useRef<AbortController | null>(null)

  useEffect(() => {
    loader.current = loadPage
  }, [loadPage])

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    moreController.current?.abort()
    cursor.current = {
      offset: 0,
      source: null,
      busy: true,
      done: false,
      ids: new Set(),
    }
    setItems([])
    setStatus('loading')
    setMore('idle')
    loader
      .current(0, null, controller.signal)
      .then((page) => {
        cursor.current = {
          offset: page.received,
          source: page.source,
          busy: false,
          done: page.done,
          ids: new Set(page.items.map((item) => item.id)),
        }
        setItems(page.items)
        setStatus('ready')
        setMore(page.done ? 'done' : 'idle')
      })
      .catch(() => {
        if (controller.signal.aborted) return
        cursor.current.busy = false
        setStatus('error')
      })
    return () => controller.abort()
  }, [resetKey, enabled, attempt])

  const loadMore = useCallback(() => {
    const current = cursor.current
    if (current.busy || current.done) return
    current.busy = true
    const controller = new AbortController()
    moreController.current = controller
    setMore('loading')
    loader
      .current(current.offset, current.source, controller.signal)
      .then((page) => {
        // A reset started a new list while this page was loading.
        if (cursor.current !== current) return
        const fresh = page.items.filter((item) => !current.ids.has(item.id))
        fresh.forEach((item) => current.ids.add(item.id))
        current.offset += page.received
        current.done = page.done
        current.busy = false
        setItems((list) => [...list, ...fresh])
        setMore(page.done ? 'done' : 'idle')
      })
      .catch(() => {
        if (controller.signal.aborted || cursor.current !== current) return
        current.busy = false
        setMore('error')
      })
  }, [])

  useEffect(() => () => moreController.current?.abort(), [])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  return {
    items,
    status,
    loadingMore: more === 'loading',
    loadMoreFailed: more === 'error',
    hasMore: more !== 'done',
    loadMore,
    reload,
  }
}

/*
 * Calls `onVisible` when the returned ref's element comes within two screens
 * of view inside `root`, the element that scrolls (the feed and Explore each
 * scroll on their own), so the next page is there before the reader gets to the end.
 * The observer is rebuilt whenever `itemCount` changes: if the end is still in
 * view after a page loaded, that fires again and loads the next one.
 */
export function useLoadMoreTrigger(
  root: RefObject<HTMLElement | null>,
  onVisible: () => void,
  itemCount: number,
  enabled: boolean,
) {
  const [element, setElement] = useState<HTMLElement | null>(null)

  useEffect(() => {
    if (!element || !enabled) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) onVisible()
      },
      { root: root.current, rootMargin: '200% 0px' },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [root, element, enabled, onVisible, itemCount])

  return setElement
}
