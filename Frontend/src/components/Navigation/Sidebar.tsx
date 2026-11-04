import { ChevronRight, Compass, LogIn, Sparkles } from 'lucide-react'
import { TOPICS, TOPIC_ICONS } from '../../data/topics'
import type { User } from '../../types'
import type { Account } from '../../utils/account'
import { AccountAvatar } from '../AccountAvatar/AccountAvatar'
import { Skeleton } from '../Skeleton/Skeleton'
import { Logo } from './Logo'
import { SearchField } from './SearchField'
import styles from './Navigation.module.css'

/* Desktop navigation. Below 820px it is replaced by MobileTopBar + MobileTabBar. */
type Props = {
  user: User
  account: Account | null
  /** True until the saved session is read, so "Log in" doesn't flash before the profile. */
  checkingSession: boolean
}

export function Sidebar({ user, account, checkingSession }: Props) {
  return (
    <aside className={styles.sidebar}>
      <Logo />
      <SearchField id="sidebar-search" />

      <nav aria-label="Main">
        <ul className={styles.mainNav}>
          <li>
            <a href="/" className={styles.navItem} aria-current="page">
              <Sparkles size={20} aria-hidden="true" />
              For You
              <span className={styles.activeDot} aria-hidden="true" />
            </a>
          </li>
          <li>
            <a href="#explore" className={styles.navItem}>
              <Compass size={20} aria-hidden="true" />
              Explore
            </a>
          </li>
        </ul>
      </nav>

      <section className={styles.topics} aria-labelledby="topics-heading">
        <div className={styles.topicsHeader}>
          <h2 id="topics-heading" className={styles.sectionTitle}>
            Topics
          </h2>
          <button type="button" className={styles.editLink}>
            Edit<span className="sr-only"> topics</span>
          </button>
        </div>
        <ul>
          {TOPICS.map((topic) => {
            const Icon = TOPIC_ICONS[topic]
            const following = user.followedTopics.includes(topic)
            return (
              <li key={topic}>
                <a href={`#topic-${topic.toLowerCase()}`} className={styles.topicRow}>
                  <span className={styles.topicIcon} aria-hidden="true">
                    <Icon size={16} />
                  </span>
                  <span className={styles.topicName}>{topic}</span>
                  {following && <span className={styles.following}>Following</span>}
                </a>
              </li>
            )
          })}
        </ul>
      </section>

      <div className={styles.account}>
        {checkingSession ? (
          <div className={styles.profile} role="status">
            <Skeleton circle width={36} height={36} />
            <span className={styles.profileText}>
              <Skeleton width="70%" height={12} />
              <Skeleton width="90%" height={10} className={styles.skeletonGap} />
            </span>
            <span className="sr-only">Checking your account…</span>
          </div>
        ) : account ? (
          <a href="#profile" className={styles.profile}>
            <AccountAvatar account={account} />
            <span className={styles.profileText}>
              <span className={styles.profileName}>{account.name}</span>
              {account.email && <span className={styles.profileEmail}>{account.email}</span>}
            </span>
            <ChevronRight size={18} className={styles.profileChevron} aria-hidden="true" />
            <span className="sr-only">, view profile</span>
          </a>
        ) : (
          <a href="#login" className={styles.loginButton}>
            <LogIn size={20} aria-hidden="true" />
            Log in
          </a>
        )}
      </div>
    </aside>
  )
}
