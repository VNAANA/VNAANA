import assert from 'node:assert/strict'
import { after, afterEach, before, test } from 'node:test'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

/*
 * Explore's title search together with the tag filter: the tags are kept in
 * the URL, the search only in memory, and both turn into GET /stories
 * requests (tag_id, q, limit, offset).
 */

const frontendRoot = fileURLToPath(new URL('../../../Frontend', import.meta.url))
const sports = 'c562c116-8f53-5d76-9cd1-30361bd511e1'
const domestic = '9bfd4082-3315-55ba-82b6-66d75e63a667'
const realFetch = globalThis.fetch
let server, explore, search

before(async () => {
  server = await createServer({
    root: frontendRoot, configFile: false, envFile: false, logLevel: 'silent',
    server: { middlewareMode: true, hmr: false, watch: null },
    define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://api.test') },
    // stories.ts imports the Supabase client; these tests never sign in.
    plugins: [{
      name: 'supabase-stub', enforce: 'pre',
      resolveId(id) { if (id === './supabase') return '\0supabase-stub' },
      load(id) {
        if (id === '\0supabase-stub')
          return 'export const supabase = { auth: { getSession: async () => ({ data: { session: null } }) } }'
      },
    }],
  })
  explore = await server.ssrLoadModule('/src/utils/explore.ts')
  search = await server.ssrLoadModule('/src/utils/search.ts')
})

afterEach(() => { globalThis.fetch = realFetch })
after(async () => { await server?.close() })

/* Calls fetchExploreStories with a fake fetch and returns the URL it requested. */
async function requested(filter, offset = 0, stories = []) {
  let url
  globalThis.fetch = async (input) => {
    url = new URL(String(input))
    return new Response(JSON.stringify(stories), { status: 200 })
  }
  await explore.fetchExploreStories(filter, offset)
  return url
}

// ---------- The search text ----------

test('the search is trimmed and spaces are collapsed', () => {
  assert.equal(explore.exploreQuery('  flood   in\tRotterdam '), 'flood in Rotterdam')
})

test('a search shorter than 2 characters is no search (the backend would reject it)', () => {
  assert.equal(explore.exploreQuery(''), '')
  assert.equal(explore.exploreQuery('   '), '')
  assert.equal(explore.exploreQuery(' a '), '')
  assert.equal(explore.exploreQuery('EU'), 'EU')
})

test('a search is cut to the backend maximum of 100 characters', () => {
  const query = explore.exploreQuery('x'.repeat(150))
  assert.equal(query.length, explore.MAX_SEARCH_CHARS)
  assert.equal(explore.MAX_SEARCH_CHARS, 100)
})

// ---------- Not in the URL, so a refresh drops it ----------

test('the URL keeps the tags but never the search', () => {
  assert.equal(explore.exploreHash({ tagIds: [sports], query: 'final' }), `#explore?tags=${sports}`)
  assert.equal(explore.exploreHash({ tagIds: [], query: 'final' }), '#explore')
})

test('a search in an old or hand-made URL is ignored', () => {
  assert.deepEqual(explore.exploreFilterFromHash(`#explore?tags=${sports}&q=final`), { tagIds: [sports], query: '' })
})

test('the list restarts when the tags or the search change, and only then', () => {
  const key = explore.exploreFilterKey
  assert.equal(key({ tagIds: [sports], query: 'final' }), key(explore.exploreFilter([sports], '  final ')))
  assert.notEqual(key({ tagIds: [sports], query: 'final' }), key({ tagIds: [sports], query: '' }))
  assert.notEqual(key({ tagIds: [sports], query: 'final' }), key({ tagIds: [domestic, sports], query: 'final' }))
})

test('the restart key gives back the same tags and search, including URL characters', () => {
  const filter = explore.exploreFilter([sports, domestic], 'AT&T 100% #1 = "win"?')
  assert.deepEqual(explore.exploreFilterFromKey(explore.exploreFilterKey(filter)), filter)
})

// ---------- The search in memory ----------

test('setting a search tells listeners once; the same search again does not', () => {
  let calls = 0
  const stop = search.subscribeSearch(() => calls++)
  search.setSearch('  flood   rotterdam ')
  search.setSearch('flood rotterdam')
  stop()
  assert.equal(search.readSearch(), 'flood rotterdam')
  assert.equal(calls, 1)
  search.setSearch('')
})

test('emptying the search bar clears the search', () => {
  search.setSearch('final')
  search.setSearch('')
  assert.equal(search.readSearch(), '')
})

test('a one-letter search is no search', () => {
  search.setSearch('a')
  assert.equal(search.readSearch(), '')
})

test('changing the tags on Explore keeps the search; leaving Explore drops it', () => {
  search.setSearch('final')
  search.keepSearchFor(`#explore?tags=${sports}`)
  assert.equal(search.readSearch(), 'final')
  search.keepSearchFor('#explore')
  assert.equal(search.readSearch(), 'final')
  search.keepSearchFor('#profile')
  assert.equal(search.readSearch(), '')
})

// ---------- The request ----------

test('no tags and no search: the first page of every story', async () => {
  const url = await requested({ tagIds: [], query: '' })
  assert.equal(url.pathname, '/stories')
  assert.equal(url.searchParams.get('limit'), String(explore.EXPLORE_SIZE))
  assert.equal(url.searchParams.get('offset'), '0')
  assert.equal(url.searchParams.has('q'), false)
  assert.equal(url.searchParams.has('tag_id'), false)
})

test('a search without tags searches every story', async () => {
  const url = await requested({ tagIds: [], query: 'flood rotterdam' })
  assert.equal(url.searchParams.get('q'), 'flood rotterdam')
  assert.deepEqual(url.searchParams.getAll('tag_id'), [])
})

test('a search with tags only searches those tags', async () => {
  const url = await requested({ tagIds: [domestic, sports], query: 'final' })
  assert.equal(url.searchParams.get('q'), 'final')
  assert.deepEqual(url.searchParams.getAll('tag_id'), [domestic, sports])
})

test('tags without a search send no q', async () => {
  const url = await requested({ tagIds: [sports], query: '' })
  assert.equal(url.searchParams.has('q'), false)
  assert.deepEqual(url.searchParams.getAll('tag_id'), [sports])
})

test('the next pages keep the search and tags and move the offset by one page', async () => {
  const filter = { tagIds: [sports], query: 'final' }
  for (const offset of [explore.EXPLORE_SIZE, explore.EXPLORE_SIZE * 2]) {
    const url = await requested(filter, offset)
    assert.equal(url.searchParams.get('offset'), String(offset))
    assert.equal(url.searchParams.get('limit'), String(explore.EXPLORE_SIZE))
    assert.equal(url.searchParams.get('q'), 'final')
    assert.deepEqual(url.searchParams.getAll('tag_id'), [sports])
  }
})

test('the page size stays inside the backend limit of 1–100', () => {
  assert.ok(explore.EXPLORE_SIZE >= 1 && explore.EXPLORE_SIZE <= 100)
})

test('a failed request is an error, not an empty result', async () => {
  globalThis.fetch = async () => new Response('{"detail":"Search must be at least 2 characters"}', { status: 400 })
  await assert.rejects(explore.fetchExploreStories({ tagIds: [], query: 'ok' }, 0))
})
