/* Date formatting shared by the feed and Explore. */
import type { Strings } from '../data/strings'

/* "2h ago" in the display language; older than a week becomes a date. */
export function timeAgo(date: Date, t: Strings) {
  const minutes = Math.round((Date.now() - date.getTime()) / 60000)
  if (minutes < 1) return t.post.timeAgo.justNow
  if (minutes < 60) return t.post.timeAgo.minutes(minutes)
  const hours = Math.round(minutes / 60)
  if (hours < 24) return t.post.timeAgo.hours(hours)
  const days = Math.round(hours / 24)
  if (days < 7) return t.post.timeAgo.days(days)
  return date.toLocaleDateString(t.locale, { day: 'numeric', month: 'short' })
}
