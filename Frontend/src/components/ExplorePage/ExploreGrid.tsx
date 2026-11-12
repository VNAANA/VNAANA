import { useState } from 'react'
import type { ExploreItem } from '../../utils/explore'
import { ExploreImageCard } from './ExploreImageCard'
import { ExploreTextTile } from './ExploreTextTile'
import styles from './ExploreGrid.module.css'

// The API has no image sizes, so image heights follow this stable pattern by position.
const IMAGE_HEIGHTS = [220, 180, 240, 200, 230, 190]

/* Masonry grid. Cards stay in data order in the DOM, so keyboard and screen reader order is the API's. */
export function ExploreGrid({ items }: { items: ExploreItem[] }) {
  return (
    <div className={styles.grid}>
      {items.map((item, index) => (
        <ExploreCard key={item.id} item={item} index={index} />
      ))}
    </div>
  )
}

/* An image card, or a text tile when there's no image or it fails to load. */
function ExploreCard({ item, index }: { item: ExploreItem; index: number }) {
  const [imageFailed, setImageFailed] = useState(false)
  if (item.imageUrl && !imageFailed) {
    return (
      <ExploreImageCard
        item={item}
        imageHeight={IMAGE_HEIGHTS[index % IMAGE_HEIGHTS.length]}
        onImageError={() => setImageFailed(true)}
      />
    )
  }
  return <ExploreTextTile item={item} />
}
