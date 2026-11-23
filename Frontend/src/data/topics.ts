import { Briefcase, Clapperboard, Cpu, FlaskConical, Globe, Landmark, Trophy } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Topic } from '../types'

/* The topics shown in the sidebar, in order, with their icons. */
export const TOPIC_ICONS: Record<Topic, LucideIcon> = {
  Technology: Cpu,
  Sports: Trophy,
  Politics: Landmark,
  Entertainment: Clapperboard,
  Science: FlaskConical,
  World: Globe,
  Business: Briefcase,
}

export const TOPICS = Object.keys(TOPIC_ICONS) as Topic[]

/* The topic a story tag is named after ("science" → Science), so it can use that topic's icon and translation. */
export function topicForTag(name: string): Topic | undefined {
  return TOPICS.find((known) => known.toLowerCase() === name.toLowerCase())
}
