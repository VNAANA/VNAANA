/*
 * Sample data for the prototype. The person is FICTIONAL.
 * Feed articles now come from the backend (see utils/articles.ts).
 */
import type { User } from '../types'

export const sampleUser: User = {
  firstName: 'Kristína',
  name: 'Kristína Straková',
  username: 'kristina.s',
  initials: 'KS',
  followedTopics: ['Technology', 'Sports', 'Science'],
}

export const briefingMeta = {
  readTime: 'About 4 min',
  updatedAt: '08:10',
}
