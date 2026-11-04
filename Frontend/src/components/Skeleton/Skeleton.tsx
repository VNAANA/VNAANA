import type { CSSProperties } from 'react'
import styles from './Skeleton.module.css'

type Props = {
  width?: CSSProperties['width']
  height?: CSSProperties['height']
  circle?: boolean
  className?: string
}

/* Placeholder in the shape of content that is still loading. Hidden from screen readers. */
export function Skeleton({ width = '100%', height = 14, circle = false, className = '' }: Props) {
  return (
    <span
      className={`${styles.block} ${circle ? styles.circle : ''} ${className}`}
      style={{ width, height }}
      aria-hidden="true"
    />
  )
}
