import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

/*
 * Opening a story from Explore shows it as a post inside the app instead of
 * going to the source. Each Explore item carries that post, built the same
 * way as a For You post; the source stays one tap away in "Read more".
 */

const frontendRoot = fileURLToPath(new URL('../../../Frontend', import.meta.url))
let server, explore, stories

before(async () => {
  server = await createServer({
    root: frontendRoot, configFile: false, envFile: false, logLevel: 'silent',
    server: { middlewareMode: true, hmr: false, watch: null },
    define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://api.test') },
    // stories.ts imports the Supabase client; these tests never sign in.
    plugins: [{
      name: 'supabase-stub', enforce: 'pre',
      resolveId(id) { if (id === './supabase') return '\0supabase-stub' },
      load(id) { if (id === '\0supabase-stub') return 'export const supabase = {}' },
    }],
  })
  explore = await server.ssrLoadModule('/src/utils/explore.ts')
  stories = await server.ssrLoadModule('/src/utils/stories.ts')
})

after(async () => { await server?.close() })

function apiStory(overrides = {}) {
  return {
    id: 'story-1',
    title: 'Floods in Rotterdam',
    context: 'First paragraph.\nSecond paragraph.',
    img_url: 'https://img.test/flood.jpg',
    articles_count: 3,
    first_published_at: '2026-11-20T08:00:00Z',
    last_updated_at: '2026-11-20T09:00:00Z',
    tags: [
      { tag: { id: 't1', name: 'Climate' }, relevance_score: 0.9 },
      { tag: { id: 't2', name: 'Domestic' }, relevance_score: 0.8 },
    ],
    // description null: the HTML-to-text step needs a browser's DOMParser.
    lead_article: {
      id: 'a1',
      title: 'Floods in Rotterdam',
      canonical_url: 'https://nos.test/floods',
      description: null,
      img_url: null,
      author: 'Sanne',
      published_at: '2026-11-20T08:00:00Z',
      provider: { name: 'NOS', reliability_status: 'verified' },
    },
    ...overrides,
  }
}

test('an Explore item carries the same post a For You story would show', () => {
  const story = apiStory()
  const { publishedAt, ...article } = explore.toExploreItem(story).article
  const { publishedAt: feedDate, feedReason: _reason, ...feed } = stories.toArticle(story)
  assert.equal(publishedAt.getTime(), feedDate.getTime())
  assert.deepEqual({ ...article, feedReason: undefined }, { ...feed, feedReason: undefined })
})

test('the post is the story itself: same id and title as the card', () => {
  const item = explore.toExploreItem(apiStory())
  assert.equal(item.article.id, item.id)
  assert.equal(item.article.title, item.title)
})

test('the card no longer links to the source; the post still does, from "Read more"', () => {
  const item = explore.toExploreItem(apiStory())
  assert.equal('href' in item, false)
  assert.equal(item.article.readMore.url, 'https://nos.test/floods')
})

test('the post can ask Nova about the story', () => {
  const item = explore.toExploreItem(apiStory())
  assert.equal(item.article.novaStory.storyId, 'story-1')
})

test('the post keeps the card\'s tags and domestic / international icon', () => {
  const item = explore.toExploreItem(apiStory())
  assert.deepEqual(item.article.tags, item.tags)
  assert.equal(item.article.scope, 'domestic')
})

test('the reader goes through the stories in the grid\'s order', () => {
  const page = ['a', 'b', 'c'].map((id) => apiStory({ id, title: `Story ${id}` }))
  assert.deepEqual(page.map(explore.toExploreItem).map((item) => item.article.id), ['a', 'b', 'c'])
})

test('a story without a lead article still opens as a post', () => {
  const item = explore.toExploreItem(apiStory({ lead_article: null }))
  assert.equal(item.article.title, 'Floods in Rotterdam')
  assert.equal(item.article.readMore.url, '')
})
