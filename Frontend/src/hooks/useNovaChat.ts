import { useRef, useState } from 'react'
import type { NovaErrorCode } from '../data/strings'
import { askNova, MAX_NOVA_QUESTION_CHARS, NovaError } from '../utils/nova'
import type { NovaAnswer, NovaExchange } from '../utils/nova'
import { readLanguage } from '../utils/language'
import type { NovaStory } from '../types'

export type ChatMessage =
  | { id: number; from: 'user'; text: string }
  | { id: number; from: 'nova'; answer: NovaAnswer }
  | { id: number; from: 'nova'; error: NovaErrorCode }

/*
 * The Ask Nova conversation for one post. Lives in FeedPost, so each story
 * keeps its own chat. Follow-up questions send the last answered exchanges
 * along; the backend doesn't store the conversation.
 */
export function useNovaChat(story?: NovaStory) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [pending, setPending] = useState(false)
  const nextId = useRef(0)
  const exchanges = useRef<NovaExchange[]>([])
  const available = !!story

  const send = async (message: string) => {
    const question = message.trim().slice(0, MAX_NOVA_QUESTION_CHARS)
    if (!question || pending || !story) return
    setMessages((list) => [
      ...list,
      { id: nextId.current++, from: 'user', text: question },
    ])
    setPending(true)
    // The answer language is set on the profile page
    const language = readLanguage()
    try {
      const answer = await askNova(
        story.storyId,
        question,
        language,
        exchanges.current,
      )
      exchanges.current = [
        ...exchanges.current,
        { question, answer: answer.text },
      ]
      setMessages((list) => [
        ...list,
        { id: nextId.current++, from: 'nova', answer },
      ])
    } catch (error) {
      setMessages((list) => [
        ...list,
        {
          id: nextId.current++,
          from: 'nova',
          error: error instanceof NovaError ? error.code : 'failed',
        },
      ])
    } finally {
      setPending(false)
    }
  }

  return {
    messages,
    pending,
    send,
    available,
    sourceLabels: story?.sourceLabels ?? {},
  }
}

export type NovaChat = ReturnType<typeof useNovaChat>
