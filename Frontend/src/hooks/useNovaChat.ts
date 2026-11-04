import { useRef, useState } from 'react'
import type { NovaErrorCode } from '../data/strings'
import { askNova, NovaError, simplifyNova } from '../utils/nova'
import type { NovaAnswer, NovaSuggestion } from '../utils/nova'
import { MAX_NOVA_ARTICLE_CHARS } from '../utils/nova'
import { readLanguage } from '../utils/language'
import type { NovaArticle } from '../types'

export type ChatMessage =
  | { id: number; from: 'user'; text: string }
  | { id: number; from: 'nova'; answer: NovaAnswer }
  | { id: number; from: 'nova'; error: NovaErrorCode }

/* The Ask Nova conversation for one post. Lives in FeedPost. */
export function useNovaChat(article?: NovaArticle) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [pending, setPending] = useState(false)
  const nextId = useRef(0)

  const submit = async (message: string, action: NovaSuggestion['action']) => {
    const text = message.trim()
    if (!text || pending || !available) return
    setMessages((list) => [...list, { id: nextId.current++, from: 'user', text }])
    setPending(true)
    // The answer language is set on the profile page
    const language = readLanguage()
    try {
      const answer = action === 'simplify'
        ? await simplifyNova(article!, language)
        : await askNova(article!, text, language)
      setMessages((list) => [...list, { id: nextId.current++, from: 'nova', answer }])
    } catch (error) {
      setMessages((list) => [
        ...list,
        { id: nextId.current++, from: 'nova', error: error instanceof NovaError ? error.code : 'failed' },
      ])
    } finally {
      setPending(false)
    }
  }

  const send = (question: string) => submit(question, 'ask')
  const sendSuggestion = (suggestion: NovaSuggestion) => submit(suggestion.label, suggestion.action)
  const tooLong = !!article && article.groundingText.length > MAX_NOVA_ARTICLE_CHARS
  const available = !!article?.groundingText.trim() && !tooLong
  return {
    messages,
    pending,
    send,
    sendSuggestion,
    available,
    tooLong,
    groundingMode: article?.groundingMode,
    previewIncludesDescription: article?.previewIncludesDescription,
  }
}

export type NovaChat = ReturnType<typeof useNovaChat>
