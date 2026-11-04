import { Anchor } from 'lucide-react'
import { useStrings } from '../../hooks/useStrings'
import styles from './Navigation.module.css'

export function Logo() {
  const { t } = useStrings()
  return (
    <a href="/" className={styles.logo} aria-label={t.nav.home}>
      <span className={styles.logoMark} aria-hidden="true">
        <Anchor size={20} strokeWidth={2.4} />
      </span>
      <span className={styles.wordmark} aria-hidden="true">
        Virtual News
        <br />
        Anchor
      </span>
    </a>
  )
}
