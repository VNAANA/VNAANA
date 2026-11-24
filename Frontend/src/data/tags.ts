import {
  Clapperboard,
  Cpu,
  FlaskConical,
  Globe,
  HeartPulse,
  House,
  Landmark,
  Leaf,
  Palette,
  Tag,
  TrendingUp,
  Trophy,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Strings } from './strings'

/*
 * How each tag looks. The tags themselves come from the database (GET /tags,
 * see utils/tags.ts). This only gives a known tag its icon; its translated
 * name is in strings.ts under `tags`. A tag that isn't listed here still
 * works: it gets the generic tag icon and its database name.
 *
 * Keyed by the tag's name in lower case, so "Social Issues" and
 * "social issues" match. Used by the sidebar, the topic editor, the Explore
 * filter and the pills on posts, so a tag looks the same everywhere.
 */
const TAG_ICONS: Record<string, LucideIcon> = {
  politics: Landmark,
  technology: Cpu,
  sports: Trophy,
  climate: Leaf,
  economy: TrendingUp,
  health: HeartPulse,
  entertainment: Clapperboard,
  'social issues': Users,
  culture: Palette,
  science: FlaskConical,
  domestic: House,
  international: Globe,
}

const key = (name: string) => name.trim().toLowerCase()

export function tagIcon(name: string): LucideIcon {
  return TAG_ICONS[key(name)] ?? Tag
}

/* The tag's name in the display language, or its database name when there's no translation. */
export function tagLabel(name: string, t: Strings): string {
  return t.tags[key(name)] ?? name
}
