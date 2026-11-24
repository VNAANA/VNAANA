import assert from 'node:assert/strict'
import { after, afterEach, before, beforeEach, test } from 'node:test'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

/*
 * The post's Translate button on the request side (utils/stories.ts):
 * POST /stories/{id}/translation with the user's token, what a failure turns
 * into, and story lists sending the token so translated stories come back
 * translated.
 */

const frontendRoot = fileURLToPath(new URL('../../../Frontend', import.meta.url))
const realFetch = globalThis.fetch
let server, stories, requests

before(async () => {
  server = await createServer({
    root: frontendRoot, configFile: false, envFile: false, logLevel: 'silent',
    server: { middlewareMode: true, hmr: false, watch: null },
    define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://api.test') },
    // The session comes from globalThis.testSession: null is signed out.
    plugins: [{
      name: 'supabase-stub', enforce: 'pre',
      resolveId(id) { if (id === './supabase') return '\0supabase-stub' },
      load(id) {
        if (id === '\0supabase-stub')
          return 'export const supabase = { auth: { getSession: async () => ({ data: { session: globalThis.testSession } }) } }'
      },
    }],
  })
  stories = await server.ssrLoadModule('/src/utils/stories.ts')
})

beforeEach(() => {
  globalThis.testSession = { access_token: 'token' }
  requests = []
})
afterEach(() => { globalThis.fetch = realFetch })
after(async () => {
  delete globalThis.DOMParser
  await server?.close()
})

// toArticle turns the HTML description into text with the browser's
// DOMParser. Node has none; these descriptions are plain text anyway.
globalThis.DOMParser ??= class {
  parseFromString(text) { return { body: { textContent: text } } }
}

/* Answers every request with the next of these responses, and remembers the requests. */
function respond(...responses) {
  globalThis.fetch = async (input, init = {}) => {
    requests.push({ url: String(input), method: init.method ?? 'GET', headers: init.headers ?? {} })
    const next = responses.shift()
    if (next instanceof Error) throw next
    const [status, body] = next
    return new Response(JSON.stringify(body), { status })
  }
}

function apiStory(overrides = {}) {
  return {
    id: 'story-1',
    title: 'Title',
    context: 'Context',
    img_url: null,
    articles_count: 1,
    first_published_at: '2026-11-24T10:00:00Z',
    last_updated_at: '2026-11-24T10:00:00Z',
    translated_into: 'en',
    tags: [],
    lead_article: {
      id: 'article-1',
      title: 'Artikel',
      canonical_url: 'https://nos.nl/artikel',
      description: 'Description',
      img_url: null,
      author: null,
      published_at: null,
      provider: { name: 'NOS', reliability_status: 'verified' },
    },
    ...overrides,
  }
}

// ---------- Translate ----------

test('Translate posts to the story with the user token', async () => {
  respond([200, apiStory()])

  const story = await stories.translateStory('story 1')

  assert.equal(story.title, 'Title')
  assert.deepEqual(requests, [{
    url: 'http://api.test/stories/story%201/translation',
    method: 'POST',
    headers: { Authorization: 'Bearer token' },
  }])
})

test('the translated story becomes the post, with its translated description', async () => {
  const article = stories.toArticle(apiStory(), 'dontMiss')

  assert.equal(article.translatedInto, 'en')
  assert.equal(article.title, 'Title')
  assert.equal(article.summary, 'Description')
  assert.equal(article.feedReason, 'dontMiss')
})

test('the story summary goes to the Why it matters part, one string per paragraph', () => {
  const article = stories.toArticle(apiStory({ summary: '  First point.\n\nSecond point.  ' }))

  assert.deepEqual(article.whySummary, ['First point.', 'Second point.'])
  // The first part keeps the lead article's description.
  assert.equal(article.summary, 'Description')
})

test('without a story summary, Why it matters has no text and shows its placeholder', () => {
  assert.equal(stories.toArticle(apiStory({ summary: null })).whySummary, undefined)
  assert.equal(stories.toArticle(apiStory({ summary: '  \n ' })).whySummary, undefined)
  // An older backend without the field.
  assert.equal(stories.toArticle(apiStory({ summary: undefined })).whySummary, undefined)
})

test('a translated summary from the backend is shown like the original', async () => {
  respond([200, apiStory({ summary: 'Translated summary', translated_into: 'en' })])

  const article = stories.toArticle(await stories.translateStory('story-1'))

  assert.deepEqual(article.whySummary, ['Translated summary'])
})

test('a story nobody translated has no translatedInto', () => {
  assert.equal(stories.toArticle(apiStory({ translated_into: null })).translatedInto, undefined)
  // An older backend without the field, or a language the app doesn't know.
  assert.equal(stories.toArticle(apiStory({ translated_into: undefined })).translatedInto, undefined)
  assert.equal(stories.toArticle(apiStory({ translated_into: 'de' })).translatedInto, undefined)
})

test('a 503 means the translation service is unavailable', async () => {
  respond([503, { detail: 'Translation quota exceeded, try again later' }])

  await assert.rejects(stories.translateStory('story-1'), { code: 'unavailable' })
})

test('other failures, or no connection, are a general failure', async () => {
  respond([404, { detail: 'Story not found' }])
  await assert.rejects(stories.translateStory('story-1'), { code: 'failed' })

  respond(new TypeError('Failed to fetch'))
  await assert.rejects(stories.translateStory('story-1'), { code: 'failed' })
})

test('signed out, Translate sends nothing', async () => {
  globalThis.testSession = null
  respond([200, apiStory()])

  await assert.rejects(stories.translateStory('story-1'), { code: 'failed' })
  assert.deepEqual(requests, [])
})

// ---------- Story lists ----------

test('signed in, story lists send the token so translations come back', async () => {
  respond([200, [apiStory()]])

  const list = await stories.fetchStories(10, 5)

  assert.equal(list[0].translated_into, 'en')
  assert.equal(requests[0].url, 'http://api.test/stories?limit=5&offset=10')
  assert.deepEqual(requests[0].headers, { Authorization: 'Bearer token' })
})

test('signed out, story lists are requested without a token', async () => {
  globalThis.testSession = null
  respond([200, []])

  await stories.fetchStories(0, 5)

  assert.deepEqual(requests[0].headers, {})
})

test('a refused token does not empty the feed: it asks again without one', async () => {
  respond([401, { detail: 'Session expired' }], [200, [apiStory({ translated_into: null })]])

  const list = await stories.fetchStories(0, 5)

  assert.equal(list.length, 1)
  assert.equal(requests.length, 2)
  assert.deepEqual(requests[1].headers, {})
})

test('a failing story list still fails', async () => {
  respond([500, {}])

  await assert.rejects(stories.fetchStories(0, 5))
})
