import { useState } from 'react'
import type { Account } from '../../utils/account'
import styles from './AccountAvatar.module.css'

/* The user's profile picture, or their initials when there is none (or it fails to load). */
export function AccountAvatar({ account, size = 38 }: { account: Account; size?: number }) {
  const [failed, setFailed] = useState(false)
  const showImage = account.avatarUrl && !failed

  return (
    <span
      className={styles.avatar}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.37) }}
      aria-hidden="true"
    >
      {showImage ? (
        <img
          className={styles.image}
          src={account.avatarUrl}
          alt=""
          // Google profile pictures refuse requests that send a referrer
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      ) : (
        account.initials
      )}
    </span>
  )
}
