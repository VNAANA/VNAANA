import { Search } from 'lucide-react'
import { useStrings } from '../../hooks/useStrings'
import styles from './Navigation.module.css'

export function SearchField({ id }: { id: string }) {
  const { t } = useStrings()
  return (
    <form className={styles.search} role="search" onSubmit={(event) => event.preventDefault()}>
      <label htmlFor={id} className="sr-only">
        {t.nav.searchLabel}
      </label>
      <Search size={18} className={styles.searchIcon} aria-hidden="true" />
      <input id={id} type="search" className={styles.searchInput} placeholder={t.nav.searchPlaceholder} autoComplete="off" />
    </form>
  )
}
