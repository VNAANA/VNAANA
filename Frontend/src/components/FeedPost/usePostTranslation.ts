import { useState } from 'react'
import { useSignedIn } from '../../hooks/useSignedIn'
import { useStrings } from '../../hooks/useStrings'
import type { Article } from '../../types'
import type { Language } from '../../utils/language'
import { toArticle, translateStory } from '../../utils/stories'

/* All news is collected in Dutch, so there is nothing to translate into Dutch. */
const SOURCE_LANGUAGE: Language = 'nl'

export type TranslationStatus = 'idle' | 'loading' | 'failed'

/*
 * The ⋯ menu's Translate for one post. The backend translates the story into
 * the user's profile language (the display language) and saves it, so the
 * feed shows it translated from then on. Here the post shows the loading
 * state, and once the translated story is back it replaces the original.
 *
 * A post the user translated before already arrives translated
 * (article.translatedInto), so Translate isn't offered for it.
 */
export function usePostTranslation(article: Article) {
  const { language } = useStrings()
  const signedIn = useSignedIn()
  const [translated, setTranslated] = useState<{
    article: Article
    language: Language
  } | null>(null)
  const [status, setStatus] = useState<TranslationStatus>('idle')

  // Only while it matches: after switching the display language, the post
  // goes back to what the feed loaded.
  const shown =
    translated &&
    translated.language === language &&
    translated.article.id === article.id
      ? translated.article
      : article

  const canTranslate =
    signedIn &&
    language !== SOURCE_LANGUAGE &&
    shown.translatedInto !== language

  const translate = async () => {
    if (status === 'loading') return
    setStatus('loading')
    try {
      const story = await translateStory(article.id)
      setTranslated({
        article: toArticle(story, article.feedReason),
        language,
      })
      setStatus('idle')
    } catch {
      setStatus('failed')
    }
  }

  return { article: shown, status, canTranslate, translate }
}

export type PostTranslation = ReturnType<typeof usePostTranslation>
