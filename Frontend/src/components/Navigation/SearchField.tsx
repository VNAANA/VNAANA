import { useState } from 'react'
import { Search } from 'lucide-react'
import { useSearch } from '../../hooks/useSearch'
import { useStrings } from '../../hooks/useStrings'
import { MAX_SEARCH_CHARS, MIN_SEARCH_CHARS, exploreQuery, isExploreHash } from '../../utils/explore'
import { setSearch } from '../../utils/search'
import styles from './Navigation.module.css'

/*
 * Searches story titles; Enter shows the results on Explore. The search stays
 * here in the bar, not in the URL or the filters, so a refresh drops it, and
 * emptying the field (or its ✕) drops it straight away. On Explore the picked
 * tags stay, so only their stories are searched; from anywhere else every story is.
 */
export function SearchField({ id }: { id: string }) {
  const { t } = useStrings()
  const query = useSearch()
  const [text, setText] = useState(query)
  const [shown, setShown] = useState(query)

  // The search changed somewhere else (the other search bar, "Clear search",
  // leaving Explore): show that one.
  if (shown !== query) {
    setShown(query)
    setText(query)
  }

  return (
    <form
      className={styles.search}
      role="search"
      onSubmit={(event) => {
        event.preventDefault()
        // Too short to search (minLength catches most of this; spaces don't count).
        if (!exploreQuery(text) && text.trim()) return
        setSearch(text)
        if (!isExploreHash(window.location.hash)) window.location.hash = '#explore'
      }}
    >
      <label htmlFor={id} className="sr-only">
        {t.nav.searchLabel}
      </label>
      <Search size={18} className={styles.searchIcon} aria-hidden="true" />
      <input
        id={id}
        type="search"
        enterKeyHint="search"
        className={styles.searchInput}
        placeholder={t.nav.searchPlaceholder}
        autoComplete="off"
        minLength={MIN_SEARCH_CHARS}
        maxLength={MAX_SEARCH_CHARS}
        value={text}
        onChange={(event) => {
          setText(event.target.value)
          if (event.target.value.trim() === '') setSearch('')
        }}
      />
    </form>
  )
}
