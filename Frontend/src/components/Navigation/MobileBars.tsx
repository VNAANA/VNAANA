import { Compass, LayoutGrid, LogIn, Sparkles } from 'lucide-react'
import { useStrings } from '../../hooks/useStrings'
import type { Account } from '../../utils/account'
import { AccountAvatar } from '../AccountAvatar/AccountAvatar'
import { Skeleton } from '../Skeleton/Skeleton'
import { Logo } from './Logo'
import { SearchField } from './SearchField'
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

// label: the key of the tab's name in the nav strings
const TABS = [
  { label: 'forYou', href: '/', Icon: Sparkles, current: true },
  { label: 'explore', href: '#explore', Icon: Compass, current: false },
  { label: 'topics', href: '#topics', Icon: LayoutGrid, current: false },
] as const

/* Bottom tab bar for screens under 820px. */
export function MobileTabBar({ account, checkingSession }: { account: Account | null; checkingSession: boolean }) {
  const { t } = useStrings()
  return (
    <nav className={styles.tabBar} aria-label={t.nav.main}>
      <ul>
        {TABS.map(({ label, href, Icon, current }) => (
          <li key={label}>
            <a href={href} className={styles.tab} aria-current={current ? 'page' : undefined}>
              <Icon size={22} aria-hidden="true" />
              {t.nav[label]}
            </a>
          </li>
        ))}
        <li>
          {checkingSession ? (
            <div className={styles.tab} role="status">
              <Skeleton circle width={22} height={22} />
              <Skeleton width={36} height={10} className={styles.skeletonGap} />
              <span className="sr-only">Checking your account…</span>
            </div>
          ) : account ? (
            <a href="#profile" className={styles.tab}>
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
    </nav>
  )
}
