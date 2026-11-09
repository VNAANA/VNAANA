import { ChevronRight, LogIn, ThumbsUp } from 'lucide-react'
import { TAG_ICONS, TAG_NAMES } from '../../data/tags'
import type { TagName } from '../../data/tags'
import { useStrings } from '../../hooks/useStrings'
import { useTopicPreferences } from '../../hooks/useTopicPreferences'
import type { Account } from '../../utils/account'
import { AccountAvatar } from '../AccountAvatar/AccountAvatar'
import { Skeleton } from '../Skeleton/Skeleton'
import { Logo } from './Logo'
import { MAIN_PAGES } from './mainPages'
import type { MainPage } from './mainPages'
import { SearchField } from './SearchField'
import styles from './Navigation.module.css'

/* Desktop navigation. Below 820px it is replaced by MobileTopBar + MobileTabBar. */
type Props = {
  account: Account | null
  /** True until the saved session is read, so "Log in" doesn't flash before the profile. */
  checkingSession: boolean
  current: MainPage
}

/* Every tag; liked ones first, the rest in the default order. */
function sidebarTags(liked: TagName[]) {
  return [...liked, ...TAG_NAMES.filter((tag) => !liked.includes(tag))]
}

export function Sidebar({ account, checkingSession, current }: Props) {
  const { t } = useStrings()
  const { liked } = useTopicPreferences().preferences
  return (
    <aside className={styles.sidebar}>
      <Logo />
      <SearchField id="sidebar-search" />

      <nav aria-label={t.nav.main}>
        <ul className={styles.mainNav}>
          {MAIN_PAGES.map(({ label, href, Icon }) => (
            <li key={label}>
              <a href={href} className={styles.navItem} aria-current={label === current ? 'page' : undefined}>
                <Icon size={20} aria-hidden="true" />
                {t.nav[label]}
                {label === current && <span className={styles.activeDot} aria-hidden="true" />}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <section className={styles.topics} aria-labelledby="topics-heading">
        <div className={styles.topicsHeader}>
          <h2 id="topics-heading" className={styles.sectionTitle}>
            {t.nav.topics}
          </h2>
          <a href="#profile" className={styles.editLink} aria-label={t.nav.editTopics}>
            {t.nav.edit}
          </a>
        </div>
        <ul>
          {sidebarTags(liked).map((tag) => {
            const Icon = TAG_ICONS[tag]
            const isLiked = liked.includes(tag)
            return (
              <li key={tag}>
                <a href={`#topic-${tag.toLowerCase()}`} className={styles.topicRow}>
                  <span className={styles.topicIcon} aria-hidden="true">
                    <Icon size={16} />
                  </span>
                  <span className={styles.topicName}>{t.tags[tag]}</span>
                  {isLiked && (
                    <>
                      <ThumbsUp size={14} className={styles.likedMark} aria-hidden="true" />
                      <span className="sr-only">{t.topicPrefs.likedMark}</span>
                    </>
                  )}
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
            <span className="sr-only">{t.nav.viewProfile}</span>
          </a>
        ) : (
          <a href="#login" className={styles.loginButton}>
            <LogIn size={20} aria-hidden="true" />
            {t.common.logIn}
          </a>
        )}
      </div>
    </aside>
  )
}
