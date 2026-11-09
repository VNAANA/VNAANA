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
  Plane,
  TrendingUp,
  Trophy,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

/*
 * The default news tags a user can like or dislike. Must match TAG_NAMES in
 * Backend/Dal/migrations/versions/c91e4a72b608_seed_default_tags.py.
 */
export const TAG_NAMES = [
  'Politics',
  'Technology',
  'Sports',
  'Climate',
  'Economy',
  'Health',
  'Entertainment',
  'World',
  'Culture',
  'Science',
  'Domestic',
  'International',
] as const

export type TagName = (typeof TAG_NAMES)[number]

export const TAG_ICONS: Record<TagName, LucideIcon> = {
  Politics: Landmark,
  Technology: Cpu,
  Sports: Trophy,
  Climate: Leaf,
  Economy: TrendingUp,
  Health: HeartPulse,
  Entertainment: Clapperboard,
  World: Globe,
  Culture: Palette,
  Science: FlaskConical,
  Domestic: House,
  International: Plane,
}
