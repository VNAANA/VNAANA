import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

const frontendRoot = fileURLToPath(new URL('../../../Frontend', import.meta.url))
const sports = 'c562c116-8f53-5d76-9cd1-30361bd511e1'
const domestic = '9bfd4082-3315-55ba-82b6-66d75e63a667'
let server, explore, tags, display, strings

// Load the application's actual TypeScript modules.
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
  tags = await server.ssrLoadModule('/src/utils/tags.ts')
  display = await server.ssrLoadModule('/src/data/tags.ts')
  strings = (await server.ssrLoadModule('/src/data/strings.ts')).STRINGS
})

after(async () => { await server?.close() })

test('no tags in the hash means All', () => {
  assert.deepEqual(explore.exploreFilterFromHash('#explore'), { tagIds: [] })
  assert.equal(explore.exploreHash({ tagIds: [] }), '#explore')
})

test('selected tags round-trip through the hash, sorted and without duplicates', () => {
  const hash = explore.exploreHash({ tagIds: [sports, domestic, sports] })
  assert.equal(hash, `#explore?tags=${domestic},${sports}`)
  assert.deepEqual(explore.exploreFilterFromHash(hash), { tagIds: [domestic, sports] })
})

test('anything in the hash that is not a tag ID is ignored', () => {
  assert.deepEqual(explore.exploreFilterFromHash(`#explore?tags=nope,${sports},<script>`), { tagIds: [sports] })
  assert.deepEqual(explore.exploreFilterFromHash('#explore?filter=science'), { tagIds: [] })
})

test('the sidebar link opens Explore filtered by that one tag', () => {
  assert.equal(explore.exploreTagHash(sports), `#explore?tags=${sports}`)
})

test('liked tags come first and disliked tags last, each group in name order', () => {
  const all = ['Climate', 'Culture', 'Economy', 'Health', 'Politics', 'Sports'].map((name) => ({ name }))
  const ordered = tags.orderByPreference(all, { liked: ['Sports', 'Culture'], disliked: ['Climate', 'Politics'] })
  assert.deepEqual(ordered.map((tag) => tag.name), ['Culture', 'Sports', 'Economy', 'Health', 'Climate', 'Politics'])
})

test('without preferences the order is unchanged', () => {
  const all = [{ name: 'B' }, { name: 'A' }]
  assert.deepEqual(tags.orderByPreference(all, { liked: [], disliked: [] }), all)
})

test('every database tag has its own icon and a Dutch name', () => {
  const generic = display.tagIcon('No such tag')
  const names = ['Climate', 'Culture', 'Domestic', 'Economy', 'Entertainment', 'Health',
    'International', 'Politics', 'Science', 'Social Issues', 'Sports', 'Technology']
  for (const name of names) {
    assert.notEqual(display.tagIcon(name), generic, `${name} has no icon`)
    assert.equal(typeof strings.nl.tags[name.toLowerCase()], 'string', `${name} has no Dutch name`)
    assert.equal(typeof strings.en.tags[name.toLowerCase()], 'string', `${name} has no English name`)
  }
  assert.equal(new Set(names.map((name) => display.tagIcon(name))).size, names.length, 'two tags share an icon')
})

test('an unknown tag keeps its database name', () => {
  assert.equal(display.tagLabel('Brand New Tag', strings.nl), 'Brand New Tag')
  assert.equal(display.tagLabel('social issues', strings.nl), 'Maatschappij')
})
