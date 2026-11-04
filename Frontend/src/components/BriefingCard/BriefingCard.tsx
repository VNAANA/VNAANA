import { X } from 'lucide-react'
import { useStrings } from '../../hooks/useStrings'
import { Segments } from '../FeedPost/CarouselControls'
import { NovaAvatar } from '../NovaAvatar/NovaAvatar'
import styles from './BriefingCard.module.css'

type Props = {
  /** Left out of the greeting when unknown */
  firstName?: string
  forYouCount: number
  dontMissCount: number
  openedCount: number
  readMinutes: number
  updatedAt: string
  onDismiss: () => void
}

/* Nova's greeting at the top of the feed, with a progress bar for today's articles. Can be dismissed. */
export function BriefingCard({ firstName, forYouCount, dontMissCount, openedCount, readMinutes, updatedAt, onDismiss }: Props) {
  const { t } = useStrings()
  const total = forYouCount + dontMissCount
  // White segments = articles opened + the one you're on now
  const filled = Math.min(openedCount + 1, total)

  return (
    <section className={styles.card} aria-labelledby="briefing-greeting">
      <NovaAvatar size={52} />
      <div className={styles.content}>
        <p className={styles.label}>{t.briefing.label}</p>
        <h1 id="briefing-greeting" className={styles.greeting}>
          {t.briefing.greeting(firstName, forYouCount, dontMissCount)}
        </h1>
        <div className={styles.progressRow}>
          <Segments total={total} filled={filled} className={styles.segments} />
          <p className={styles.meta}>
            <span className="sr-only">{t.briefing.opened(openedCount, total)}</span>
            {t.briefing.meta(readMinutes, updatedAt)}
          </p>
        </div>
      </div>
      <button type="button" className={styles.dismiss} onClick={onDismiss} aria-label={t.briefing.dismiss}>
        <X size={20} aria-hidden="true" />
      </button>
    </section>
  )
}
