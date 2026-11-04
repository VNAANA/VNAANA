import type { CSSProperties, ReactNode } from 'react'
import { useStrings } from '../../hooks/useStrings'
import { CarouselArrows, CounterPill } from './CarouselControls'
import { usePost } from './PostContext'
import styles from './PostCarousel.module.css'

type PartPadding = { top?: number; bottom?: number }

type Props = {
  /** One element per part: What happened, Why it matters, (Full article,) Read more. */
  parts: ReactNode[]
  /** Class that sets the size (--parts-h). */
  className?: string
  /** Extra room inside the text parts, e.g. to clear the "1 / 3" pill. */
  partPadding?: PartPadding
}

/*
 * The side-to-side story carousel. Every part has the same height,
 * so moving between parts never changes the size of the post.
 * Arrow keys and touch swipes work when it has focus / is touched.
 * The arrows are vertically centred; on narrow carousels they move to the bottom corners.
 */
export function PostCarousel({ parts, className = '', partPadding }: Props) {
  const { story, carousel, partIds, partLabels } = usePost()
  const { t } = useStrings()

  const paddingVars = {
    '--part-pad-top': partPadding?.top && `${partPadding.top}px`,
    '--part-pad-bottom': partPadding?.bottom && `${partPadding.bottom}px`,
  } as CSSProperties

  return (
    <div className={`${styles.wrap} ${className}`}>
      <div
        className={styles.viewport}
        style={paddingVars}
        role="region"
        aria-roledescription={t.post.carousel.roleCarousel}
        aria-label={t.post.carousel.label(story.title, carousel.count)}
        tabIndex={0}
        {...carousel.keyHandlers}
        {...carousel.swipeHandlers}
      >
        <div className={styles.track} style={{ transform: `translateX(${carousel.index * -100}%)` }}>
          {parts.map((part, i) => (
            <div
              key={partIds[i]}
              id={partIds[i]}
              className={styles.slide}
              role="group"
              aria-roledescription={t.post.carousel.rolePart}
              aria-label={t.post.carousel.partLabel(i + 1, carousel.count, partLabels[i])}
              inert={i !== carousel.index}
            >
              {part}
            </div>
          ))}
        </div>
      </div>

      <CounterPill />
      <CarouselArrows />

      <p className="sr-only" aria-live="polite">
        {t.post.carousel.announce(carousel.index + 1, carousel.count, partLabels[carousel.index])}
      </p>
    </div>
  )
}
