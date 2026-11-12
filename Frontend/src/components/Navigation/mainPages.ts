import { Compass, Sparkles } from 'lucide-react'

// label: the key of the page's name in the nav strings
export const MAIN_PAGES = [
  { label: 'forYou', href: '/', Icon: Sparkles },
  { label: 'explore', href: '#explore', Icon: Compass },
] as const

/* The page shown next to the navigation, marked as current in the sidebar and tab bar. */
export type MainPage = (typeof MAIN_PAGES)[number]['label']
