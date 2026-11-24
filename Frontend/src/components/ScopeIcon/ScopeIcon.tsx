import { tagIcon } from '../../data/tags'
import { useStrings } from '../../hooks/useStrings'
import type { NewsScope } from '../../types'
import styles from './ScopeIcon.module.css'

/*
 * Domestic or international news as a small round icon (home or globe)
 * instead of a tag pill. The caller places it in a corner. Screen readers
 * read "Domestic news" / "International news"; hovering shows the same.
 */
export function ScopeIcon({ scope, className }: { scope?: NewsScope; className?: string }) {
  const { t } = useStrings()
  if (!scope) return null
  // The same icon the Domestic / International tag has in the sidebar (house / globe).
  const Icon = tagIcon(scope)
  const label = t.post.scope[scope]
  return (
    <span className={className ? `${styles.icon} ${className}` : styles.icon} role="img" aria-label={label} title={label}>
      <Icon size={16} aria-hidden="true" />
    </span>
  )
}
