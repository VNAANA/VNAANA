/*
 * The Profile page's tabs and how the active one is kept in the URL hash:
 * "#profile" is the first tab, "#profile?tab=topics" another one.
 * To add a tab: add it here, give it a label in strings.ts (profile.tabs)
 * and a panel in ProfilePage.
 */
export const PROFILE_TABS = ['settings', 'topics'] as const

export type ProfileTab = (typeof PROFILE_TABS)[number]

/* "#profile" or "#profile?tab=topics" */
export function isProfileHash(hash: string) {
  return hash.split('?')[0] === '#profile'
}

/* The tab in the hash; unknown or missing tabs fall back to the first one. */
export function profileTabFromHash(hash: string): ProfileTab {
  const tab = new URLSearchParams(hash.split('?')[1] ?? '').get('tab')
  return PROFILE_TABS.find((known) => known === tab) ?? PROFILE_TABS[0]
}

export function profileHash(tab: ProfileTab) {
  return tab === PROFILE_TABS[0] ? '#profile' : `#profile?tab=${tab}`
}
