import { useEffect, useRef } from 'react'
import { ExternalLink, Info } from 'lucide-react'
import { useStrings } from '../../../hooks/useStrings'
import { NovaChatLog, NovaComposer } from '../NovaChat'
import { usePost } from '../PostContext'
import styles from './Parts.module.css'

/* The three parts of an article. FeedPost puts these inside a carousel. */

/* Articles from the API have no image yet: show the publisher on a plain panel instead. */
function ArticleImage({ className = '' }: { className?: string }) {
  const { article } = usePost()
  if (!article.image) {
    return (
      <div className={`${styles.imageFallback} ${className}`} aria-hidden="true">
        <span className={styles.imageFallbackName}>{article.publisher.name}</span>
      </div>
    )
  }
  return (
    <img
      className={`${styles.image} ${className}`}
      src={article.image.src}
      alt={article.image.alt}
      width={1200}
      height={800}
      draggable={false}
    />
  )
}

/* Part 1: headline and summary, then the image. They swipe away as one. */
export function WhatHappenedPart() {
  const { article, titleId } = usePost()
  return (
    <div className={styles.whatHappened}>
      <div className={styles.leadText}>
        <h2 id={titleId} className={styles.headline}>
          {article.title}
        </h2>
        <p className={styles.summary}>{article.summary}</p>
      </div>
      <ArticleImage className={styles.leadImage} />
    </div>
  )
}

export function WhyPart() {
  const { article } = usePost()
  const { t } = useStrings()
  const { why, aiNote } = article
  const uncertainty = aiNote.uncertainty ?? t.post.why.notCompared

  // No analysis from Nova yet: point to where the reader can find the article itself.
  if (!why) {
    return (
      <div className={styles.part}>
        <p className={styles.eyebrow}>{t.post.parts.why}</p>
        <h3 className={styles.heading}>{t.post.why.notExplained}</h3>
        <p className={styles.background}>
          {article.content ? t.post.why.readNextSlide : t.post.why.readOnPublisher(article.publisher.name)}
        </p>
        <p className={styles.aiNote}>
          <Info size={16} aria-hidden="true" />
          <span>{uncertainty}</span>
        </p>
      </div>
    )
  }

  return (
    <div className={styles.part}>
      <p className={styles.eyebrow}>{t.post.parts.why}</p>
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
        <strong>{t.post.why.background}</strong> {why.background}
      </p>
      <p className={styles.aiNote}>
        <Info size={16} aria-hidden="true" />
        <span>
          {t.post.why.aiSummary(aiNote.sourceCount)} · {uncertainty}
        </span>
      </p>
    </div>
  )
}

/* Only for articles whose text was scraped: the whole article, scrollable. */
export function FullArticlePart() {
  const { article } = usePost()
  const { t } = useStrings()
  const { readMinutes } = article.readMore
  return (
    <div className={styles.part}>
      <p className={styles.eyebrow}>{t.post.parts.fullArticle}</p>
      <h3 className={styles.heading}>{article.title}</h3>
      <p className={styles.articleMeta}>
        {article.publisher.name}
        {article.author && ` · ${article.author}`}
        {readMinutes && ` · ${t.post.readMore.minRead(readMinutes)}`}
      </p>
      <div className={styles.articleBody}>
        {article.content?.map((paragraph, i) => (
          <p key={i}>{paragraph}</p>
        ))}
      </div>
    </div>
  )
}

/* Last part: the original source, other perspectives, and the Ask Nova chat. */
export function ReadMorePart() {
  const { article, actions, chat } = usePost()
  const { t } = useStrings()
  const { readMore } = article
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
          <span className={styles.sourceLabel}>{t.post.readMore.fullStoryOn(article.publisher.name)}</span>
          <span className={styles.sourceTitle}>{article.title}</span>
          <span className={styles.sourceMeta}>
            {readMore.readMinutes ? t.post.readMore.minRead(readMore.readMinutes) : t.post.readMore.readArticle}
            <ExternalLink size={15} aria-hidden="true" />
            <span className="sr-only">{t.common.opensInNewTab}</span>
          </span>
        </a>

        {readMore.perspectives.length > 0 && (
          <>
            <h3 className={styles.subhead}>{t.post.readMore.otherPerspectives}</h3>
            <ul className={styles.perspectives}>
              {readMore.perspectives.map((perspective) => (
                <li key={perspective.url}>
                  <a className={styles.perspective} href={perspective.url} target="_blank" rel="noopener noreferrer">
                    <span>
                      <span className={styles.perspectivePublisher}>{perspective.publisher}</span>
                      <span className={styles.perspectiveAngle}>{perspective.angle}</span>
                    </span>
                    <ExternalLink size={15} aria-hidden="true" />
                    <span className="sr-only">{t.common.opensInNewTab}</span>
                  </a>
                </li>
              ))}
            </ul>
          </>
        )}

        <h3 className={styles.subhead}>{t.post.readMore.stillCurious}</h3>
        <NovaChatLog />
      </div>
      <NovaComposer />
    </div>
  )
}
