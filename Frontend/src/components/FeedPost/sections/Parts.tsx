import { useEffect, useRef } from 'react'
import { ExternalLink, Info } from 'lucide-react'
import { NovaChatLog, NovaComposer } from '../NovaChat'
import { usePost } from '../PostContext'
import styles from './Parts.module.css'

/* The three parts of a story. FeedPost puts these inside a carousel. */

function plural(count: number, one: string, many: string) {
  return `${count} ${count === 1 ? one : many}`
}

/* Articles from the API have no image yet: show the publisher on a plain panel instead. */
function StoryImage({ className = '' }: { className?: string }) {
  const { story } = usePost()
  if (!story.image) {
    return (
      <div className={`${styles.imageFallback} ${className}`} aria-hidden="true">
        <span className={styles.imageFallbackName}>{story.publisher.name}</span>
      </div>
    )
  }
  return (
    <img
      className={`${styles.image} ${className}`}
      src={story.image.src}
      alt={story.image.alt}
      width={1200}
      height={800}
      draggable={false}
    />
  )
}

/* Part 1: headline and summary, then the image. They swipe away as one. */
export function WhatHappenedPart() {
  const { story, titleId } = usePost()
  return (
    <div className={styles.whatHappened}>
      <div className={styles.leadText}>
        <h2 id={titleId} className={styles.headline}>
          {story.title}
        </h2>
        <p className={styles.summary}>{story.summary}</p>
      </div>
      <StoryImage className={styles.leadImage} />
    </div>
  )
}

export function WhyPart() {
  const { story } = usePost()
  const { why, aiNote } = story

  // No analysis from Nova yet: point to where the reader can find the story itself.
  if (!why) {
    return (
      <div className={styles.part}>
        <p className={styles.eyebrow}>Why it matters</p>
        <h3 className={styles.heading}>Nova hasn’t explained this one yet</h3>
        <p className={styles.background}>
          {story.content
            ? 'Until then, you can read the whole article on the next slide.'
            : `The full text isn’t available here yet. Read it on ${story.publisher.name}.`}
        </p>
        <p className={styles.aiNote}>
          <Info size={16} aria-hidden="true" />
          <span>{aiNote.uncertainty}</span>
        </p>
      </div>
    )
  }

  return (
    <div className={styles.part}>
      <p className={styles.eyebrow}>Why it matters</p>
      <h3 className={styles.heading}>{why.heading}</h3>
      <ol className={styles.points}>
        {why.points.map((point, i) => (
          <li key={point.keyword} className={styles.point}>
            <span className={styles.number} aria-hidden="true">
              {i + 1}
            </span>
            <p>
              <strong>{point.keyword}.</strong> {point.text}
            </p>
          </li>
        ))}
      </ol>
      <p className={styles.background}>
        <strong>Background:</strong> {why.background}
      </p>
      <p className={styles.aiNote}>
        <Info size={16} aria-hidden="true" />
        <span>
          AI summary from {plural(aiNote.sourceCount, 'source', 'sources')} · {aiNote.uncertainty}
        </span>
      </p>
    </div>
  )
}

/* Only for stories whose article text was scraped: the whole article, scrollable. */
export function FullArticlePart() {
  const { story } = usePost()
  return (
    <div className={styles.part}>
      <p className={styles.eyebrow}>Full article</p>
      <h3 className={styles.heading}>{story.title}</h3>
      <p className={styles.articleMeta}>
        {story.publisher.name}
        {story.author && ` · ${story.author}`}
        {story.readMore.readTime && ` · ${story.readMore.readTime}`}
      </p>
      <div className={styles.articleBody}>
        {story.content?.map((paragraph, i) => (
          <p key={i}>{paragraph}</p>
        ))}
      </div>
    </div>
  )
}

/* Last part: the original source, other perspectives, and the Ask Nova chat. */
export function ReadMorePart() {
  const { story, actions, chat } = usePost()
  const { readMore } = story
  const scrollRef = useRef<HTMLDivElement>(null)

  // Keep the newest chat message in view
  useEffect(() => {
    const area = scrollRef.current
    if (area && chat.messages.length > 0) area.scrollTo({ top: area.scrollHeight, behavior: 'smooth' })
  }, [chat.messages.length, chat.pending])

  return (
    <div className={`${styles.part} ${styles.readMore}`}>
      {/* Everything above the chat input scrolls; the input stays pinned at the bottom */}
      <div ref={scrollRef} className={styles.readMoreScroll}>
        <a
          className={styles.sourceCard}
          href={readMore.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={actions.markOpened}
        >
          <span className={styles.sourceLabel}>Full story on {story.publisher.name}</span>
          <span className={styles.sourceTitle}>{story.title}</span>
          <span className={styles.sourceMeta}>
            {readMore.readTime ?? 'Read the article'}
            <ExternalLink size={15} aria-hidden="true" />
            <span className="sr-only">(opens in a new tab)</span>
          </span>
        </a>

        {readMore.perspectives.length > 0 && (
          <>
            <h3 className={styles.subhead}>Other perspectives</h3>
            <ul className={styles.perspectives}>
              {readMore.perspectives.map((perspective) => (
                <li key={perspective.url}>
                  <a className={styles.perspective} href={perspective.url} target="_blank" rel="noopener noreferrer">
                    <span>
                      <span className={styles.perspectivePublisher}>{perspective.publisher}</span>
                      <span className={styles.perspectiveAngle}>{perspective.angle}</span>
                    </span>
                    <ExternalLink size={15} aria-hidden="true" />
                    <span className="sr-only">(opens in a new tab)</span>
                  </a>
                </li>
              ))}
            </ul>
          </>
        )}

        <h3 className={styles.subhead}>Still curious? Ask Nova</h3>
        <NovaChatLog />
      </div>
      <NovaComposer />
    </div>
  )
}
