import { Bookmark, Check, EyeOff, Heart, Share2, Sparkles, ThumbsDown } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useStrings } from '../../hooks/useStrings'
import { usePost } from './PostContext'
import styles from './ReactionBar.module.css'

export type ActionKind = 'like' | 'dislike' | 'notInterested' | 'share' | 'save'

/* One reaction button. Reads its state from the post, so it can be placed anywhere. */
export function ActionButton({ kind }: { kind: ActionKind }) {
  const { actions } = usePost()
  const { t } = useStrings()
  const labels = t.post.reactions

  const config: Record<ActionKind, { label: string; Icon: LucideIcon; onClick: () => void; pressed?: boolean }> = {
    like: { label: labels.like, Icon: Heart, onClick: actions.toggleLike, pressed: actions.liked },
    dislike: { label: labels.dislike, Icon: ThumbsDown, onClick: actions.toggleDislike, pressed: actions.disliked },
    notInterested: { label: t.post.notInterested, Icon: EyeOff, onClick: actions.hide },
    share: {
      label: actions.linkCopied ? labels.linkCopied : labels.share,
      Icon: actions.linkCopied ? Check : Share2,
      onClick: actions.share,
    },
    save: { label: actions.saved ? labels.saved : labels.save, Icon: Bookmark, onClick: actions.toggleSave, pressed: actions.saved },
  }
  const { label, Icon, onClick, pressed } = config[kind]

  return (
    <button
      type="button"
      className={styles.action}
      onClick={onClick}
      aria-pressed={pressed}
      aria-label={kind === 'notInterested' ? labels.notInterested : label}
      title={label}
    >
      <Icon size={20} aria-hidden="true" fill={pressed ? 'currentColor' : 'none'} />
    </button>
  )
}

export function AskNovaButton() {
  const { actions } = usePost()
  const { t } = useStrings()
  return (
    <button type="button" className={styles.ask} onClick={() => actions.askNova()}>
      <Sparkles size={18} aria-hidden="true" />
      {t.nova.askNova}
    </button>
  )
}

/* A row of reaction buttons with the Ask Nova button at the end. */
export function ReactionBar({ kinds }: { kinds: ActionKind[] }) {
  const { t } = useStrings()
  return (
    <div className={styles.bar} role="group" aria-label={t.post.reactions.group}>
      {kinds.map((kind) => (
        <ActionButton key={kind} kind={kind} />
      ))}
      <div className={styles.end}>
        <AskNovaButton />
      </div>
    </div>
  )
}
