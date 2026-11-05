import { useCallback, useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import { BriefingCard } from './components/BriefingCard/BriefingCard'
import { ExplorePage } from './components/ExplorePage/ExplorePage'
import { FeedPost } from './components/FeedPost/FeedPost'
import { PostSkeleton } from './components/FeedPost/PostSkeleton'
import { LoginPage } from './components/LoginPage/LoginPage'
import { MobileTabBar, MobileTopBar } from './components/Navigation/MobileBars'
import { Sidebar } from './components/Navigation/Sidebar'
import { ProfilePage } from './components/ProfilePage/ProfilePage'
import { useHash } from './hooks/useHash'
import { useAuth } from './hooks/useAuth'
import { useFeedArticles } from './hooks/useFeedArticles'
import { useStrings } from './hooks/useStrings'
import { getAccount } from './utils/account'
import { exploreFilterFromHash, isExploreHash } from './utils/explore'
import { readStorage, writeStorage } from './utils/storage'
import styles from './App.module.css'

// Session storage: the briefing comes back in a new browser session, like a new morning notification.
const BRIEFING_STORAGE_KEY = 'vnaana.briefingDismissed'

export default function App() {
  const hash = useHash()
  const auth = useAuth()
  const feed = useFeedArticles()
  const { t } = useStrings()
  const metadata = auth.session?.user.user_metadata
  const displayName = [metadata?.given_name, metadata?.full_name, metadata?.name]
    .find((value): value is string => typeof value === 'string' && value.trim().length > 0)
  const firstName = displayName?.trim()
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
  if (isExploreHash(hash)) {
    return (
      <div className={styles.app}>
        {/* "#explore" would also set the filter, so the skip link moves focus itself. */}
        <a href="#explore" className={styles.skipLink} onClick={skipToMain}>
          {t.explore.skipToContent}
        </a>
        <Sidebar account={account} checkingSession={auth.checkingSession} current="explore" />
        <MobileTopBar />
        <ExplorePage filter={exploreFilterFromHash(hash)} />
        <MobileTabBar account={account} checkingSession={auth.checkingSession} current="explore" />
      </div>
    )
  }

  const articles = feed.articles
  const forYouCount = articles.filter((article) => article.feedReason === 'forYou').length
  // Articles without scraped content have no read time; count those as a one-minute skim.
  const readMinutes = articles.reduce((sum, article) => sum + (article.readMore.readMinutes ?? 1), 0)
  const newest = articles.reduce<Date | undefined>(
    (latest, article) => (!latest || article.publishedAt > latest ? article.publishedAt : latest),
    undefined,
  )

  return (
    <div className={styles.app}>
      <a href="#feed" className={styles.skipLink}>
        {t.feed.skipToFeed}
      </a>
      <Sidebar account={account} checkingSession={auth.checkingSession} current="forYou" />
      <MobileTopBar />

      {/*
        The feed scrolls on its own and snaps to one post at a time:
        every post sits in a full-height "slide".
      */}
      <main ref={feedRef} id="feed" className={styles.feed} tabIndex={-1} aria-label={t.feed.label}>
        {auth.backendStatus && <p role="status">{t.auth[auth.backendStatus]}</p>}
        {!briefingDismissed && feed.status === 'ready' && (
          <div className={styles.intro}>
            <div className={styles.column}>
              <BriefingCard
                firstName={firstName}
                forYouCount={forYouCount}
                dontMissCount={articles.length - forYouCount}
                openedCount={openedIds.size}
                readMinutes={readMinutes}
                updatedAt={newest ? updatedLabel(newest, t.locale) : ''}
                onDismiss={dismissBriefing}
              />
            </div>
          </div>
        )}

        {feed.status === 'loading' && (
          <div className={styles.slide}>
            <div className={styles.column}>
              <p className="sr-only" role="status">
                {t.feed.loading}
              </p>
              <PostSkeleton />
            </div>
          </div>
        )}
        {feed.status === 'error' && (
          <div className={styles.feedMessage} role="alert">
            <p>{t.feed.loadFailed}</p>
            <button type="button" className={styles.retry} onClick={feed.reload}>
              {t.feed.retry}
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
            <p>{t.feed.caughtUp}</p>
          </footer>
        )}
      </main>

      <MobileTabBar account={account} checkingSession={auth.checkingSession} current="forYou" />
    </div>
  )
}

function skipToMain(event: MouseEvent<HTMLAnchorElement>) {
  event.preventDefault()
  document.querySelector<HTMLElement>('main')?.focus()
}

/* "08:10" for today, "4 Nov 08:10" for older articles. */
function updatedLabel(date: Date, locale: string) {
  const time = date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
  if (date.toDateString() === new Date().toDateString()) return time
  return `${date.toLocaleDateString(locale, { day: 'numeric', month: 'short' })} ${time}`
}
