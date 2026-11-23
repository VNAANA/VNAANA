import { useState } from 'react'
import { LayoutGrid, LogIn } from 'lucide-react'
import { useStrings } from '../../hooks/useStrings'
import type { Account } from '../../utils/account'
import { AccountAvatar } from '../AccountAvatar/AccountAvatar'
import { Skeleton } from '../Skeleton/Skeleton'
import { Logo } from './Logo'
import { MAIN_PAGES } from './mainPages'
import type { MainPage } from './mainPages'
import { SearchField } from './SearchField'
import { TopicsSheet } from './TopicsSheet'
import { TopicPreferencesDialog } from '../TopicPreferences/TopicPreferencesDialog'
import styles from './Navigation.module.css'

/* Top bar for screens under 820px: logo + search. */
export function MobileTopBar() {
  return (
    <header className={styles.topBar}>
      <Logo />
      <SearchField id="mobile-search" />
    </header>
  )
}

type TabBarProps = {
  account: Account | null
  checkingSession: boolean
  current: MainPage | 'profile'
}

/* Bottom tab bar for screens under 820px. */
export function MobileTabBar({
  account,
  checkingSession,
  current,
}: TabBarProps) {
  const { t } = useStrings()
  // Topics opens a sheet; its Edit swaps the sheet for the topic preferences pop-up.
  const [open, setOpen] = useState<'none' | 'topics' | 'editTopics'>('none')
  return (
    <nav className={styles.tabBar} aria-label={t.nav.main}>
      <ul>
        {MAIN_PAGES.map(({ label, href, Icon }) => (
          <li key={label}>
            <a
              href={href}
              className={styles.tab}
              aria-current={label === current ? 'page' : undefined}
            >
              <Icon size={22} aria-hidden="true" />
              {t.nav[label]}
            </a>
          </li>
        ))}
        <li>
          <button
            type="button"
            className={styles.tab}
            aria-haspopup="dialog"
            aria-expanded={open === 'topics'}
            onClick={() => setOpen('topics')}
          >
            <LayoutGrid size={22} aria-hidden="true" />
            {t.nav.topics}
          </button>
        </li>
        <li>
          {checkingSession ? (
            <div className={styles.tab} role="status">
              <Skeleton circle width={22} height={22} />
              <Skeleton width={36} height={10} className={styles.skeletonGap} />
              <span className="sr-only">Checking your account…</span>
            </div>
          ) : account ? (
            <a
              href="#profile"
              className={styles.tab}
              aria-current={current === 'profile' ? 'page' : undefined}
            >
              <AccountAvatar account={account} size={22} />
              {t.nav.profile}
            </a>
          ) : (
            <a href="#login" className={styles.tab}>
              <LogIn size={22} aria-hidden="true" />
              {t.common.logIn}
            </a>
          )}
        </li>
      </ul>

      {open === 'topics' && (
        <TopicsSheet
          canEdit={!!account}
          onEdit={() => setOpen('editTopics')}
          onClose={() => setOpen('none')}
        />
      )}
      {account && open === 'editTopics' && (
        <TopicPreferencesDialog mode="edit" onClose={() => setOpen('none')} />
      )}
    </nav>
  )
}
