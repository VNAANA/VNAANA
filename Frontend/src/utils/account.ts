import type { Session } from '@supabase/supabase-js'

export type Account = {
  name: string
  email?: string
  /** Profile picture from the sign-in provider (Google), if there is one */
  avatarUrl?: string
  initials: string
}

function firstText(...values: unknown[]) {
  return values.find((value): value is string => typeof value === 'string' && value.trim().length > 0)?.trim()
}

/* What the UI shows about the signed-in user. The backend profile has no name or email, so this reads the session. */
export function getAccount(session: Session | null): Account | null {
  if (!session) return null
  const { email, user_metadata: metadata = {} } = session.user
  const name = firstText(metadata.full_name, metadata.name, email?.split('@')[0]) ?? 'Your account'
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('')

  return {
    name,
    email: email || undefined,
    avatarUrl: firstText(metadata.avatar_url, metadata.picture),
    initials,
  }
}
