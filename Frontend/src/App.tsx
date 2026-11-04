import { useCallback, useRef, useState } from 'react'
import { BriefingCard } from './components/BriefingCard/BriefingCard'
import { FeedPost } from './components/FeedPost/FeedPost'
import { PostSkeleton } from './components/FeedPost/PostSkeleton'
import { LoginPage } from './components/LoginPage/LoginPage'
import { MobileTabBar, MobileTopBar } from './components/Navigation/MobileBars'
import { Sidebar } from './components/Navigation/Sidebar'
import { ProfilePage } from './components/ProfilePage/ProfilePage'
import { briefingMeta, sampleUser } from './data/sampleData'
import { useHash } from './hooks/useHash'
import { useAuth } from './hooks/useAuth'
import { useFeedArticles } from './hooks/useFeedArticles'
import { getAccount } from './utils/account'
import { readStorage, writeStorage } from './utils/storage'
import styles from './App.module.css'

// Session storage: the briefing comes back in a new browser session, like a new morning notification.
const BRIEFING_STORAGE_KEY = 'vnaana.briefingDismissed'

export default function App() {
  const hash = useHash()
  const auth = useAuth()
  const feed = useFeedArticles()
  const metadata = auth.session?.user.user_metadata
  const displayName = [metadata?.given_name, metadata?.full_name, metadata?.name]
    .find((value): value is string => typeof value === 'string' && value.trim().length > 0)
  const firstName = displayName?.trim() || 'there'
  const [openedIds, setOpenedIds] = useState<Set<string>>(() => new Set())
  const [briefingDismissed, setBriefingDismissed] = useState(
    () => readStorage(BRIEFING_STORAGE_KEY, 'session') === 'true',
  )
  const feedRef = useRef<HTMLElement>(null)

  const dismissBriefing = () => {
    setBriefingDismissed(true)
    writeStorage(BRIEFING_STORAGE_KEY, 'true', 'session')
    // The close button disappears, so move keyboard focus to the feed.
    feedRef.current?.focus()
  }

  const markOpened = useCallback((articleId: string) => {
    setOpenedIds((ids) => (ids.has(articleId) ? ids : new Set(ids).add(articleId)))
  }, [])

  if (hash === '#login') return <LoginPage auth={auth} />
  if (hash === '#profile') return <ProfilePage auth={auth} />

  const account = getAccount(auth.session)
  const articles = feed.articles
  const forYouCount = articles.filter((article) => article.feedReason === 'forYou').length

  return (
    <div className={styles.app}>
      <a href="#feed" className={styles.skipLink}>
        Skip to feed
      </a>
      <Sidebar user={sampleUser} account={account} checkingSession={auth.checkingSession} />
      <MobileTopBar />

      {/*
        The feed scrolls on its own and snaps to one post at a time:
        every post sits in a full-height "slide".
      */}
      <main ref={feedRef} id="feed" className={styles.feed} tabIndex={-1} aria-label="For You feed">
        {auth.backendStatus && <p role="status">{auth.backendStatus}</p>}
        {!briefingDismissed && feed.status === 'ready' && (
          <div className={styles.intro}>
            <div className={styles.column}>
              <BriefingCard
                firstName={firstName}
                forYouCount={forYouCount}
                dontMissCount={articles.length - forYouCount}
                openedCount={openedIds.size}
                readTime={briefingMeta.readTime}
                updatedAt={briefingMeta.updatedAt}
                onDismiss={dismissBriefing}
              />
            </div>
          </div>
        )}

        {feed.status === 'loading' && (
          <div className={styles.slide}>
            <div className={styles.column}>
              <p className="sr-only" role="status">
                Nova is gathering today’s articles for you...
              </p>
              <PostSkeleton />
            </div>
          </div>
        )}
        {feed.status === 'error' && (
          <div className={styles.feedMessage} role="alert">
            <p>We couldn’t load the news right now.</p>
            <button type="button" className={styles.retry} onClick={feed.reload}>
              Try again
            </button>
          </div>
        )}

        {articles.map((article) => (
          <div key={article.id} className={styles.slide}>
            <div className={styles.column}>
              <FeedPost article={article} onOpened={markOpened} />
            </div>
          </div>
        ))}

        {feed.status === 'ready' && (
          <footer className={styles.feedEnd}>
            <p>You’re all caught up for this morning.</p>
          </footer>
        )}
      </main>

      <MobileTabBar account={account} checkingSession={auth.checkingSession} />
    </div>
  )
}
