import { Compass, LayoutGrid, LogIn, Sparkles } from 'lucide-react'
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

const TABS = [
  { label: 'For You', href: '/', Icon: Sparkles, current: true },
  { label: 'Explore', href: '#explore', Icon: Compass },
  { label: 'Topics', href: '#topics', Icon: LayoutGrid },
]

/* Bottom tab bar for screens under 820px. */
export function MobileTabBar({ account, checkingSession }: { account: Account | null; checkingSession: boolean }) {
  return (
    <nav className={styles.tabBar} aria-label="Main">
      <ul>
        {TABS.map(({ label, href, Icon, current }) => (
          <li key={label}>
            <a href={href} className={styles.tab} aria-current={current ? 'page' : undefined}>
              <Icon size={22} aria-hidden="true" />
              {label}
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
              Profile
            </a>
          ) : (
            <a href="#login" className={styles.tab}>
              <LogIn size={22} aria-hidden="true" />
              Log in
            </a>
          )}
        </li>
      </ul>
    </nav>
  )
}
