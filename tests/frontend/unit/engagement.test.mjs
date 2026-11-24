import assert from 'node:assert/strict'
import { after, before, beforeEach, test } from 'node:test'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

/*
 * Like / Not interested (dislike), share and read: what is sent to the
 * backend, and when nothing may be sent (signed out, no consent).
 */

const frontendRoot = fileURLToPath(new URL('../../../Frontend', import.meta.url))
const USER = '11111111-1111-4111-8111-111111111111'
const STORY = '22222222-2222-4222-8222-222222222222'
const OTHER = '33333333-3333-4333-8333-333333333333'
const realFetch = globalThis.fetch
let server, engagement, topics, requests, respond

before(async () => {
  server = await createServer({
    root: frontendRoot, configFile: false, envFile: false, logLevel: 'silent',
    server: { middlewareMode: true, hmr: false, watch: null },
    define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://api.test') },
    // A signed-in Supabase session with a token; the tests never talk to Supabase.
    plugins: [{
      name: 'supabase-stub', enforce: 'pre',
      resolveId(id) { if (id === './supabase') return '\0supabase-stub' },
      load(id) {
        if (id === '\0supabase-stub') {
          return 'export const supabase = { auth: { getSession: async () => ({ data: { session: { access_token: "token" } } }) } }'
        }
      },
    }],
  })
  engagement = await server.ssrLoadModule('/src/utils/engagement.ts')
  topics = await server.ssrLoadModule('/src/utils/topicPreferences.ts')
})

after(async () => {
  globalThis.fetch = realFetch
  await server?.close()
})

beforeEach(() => {
  topics.clearTopicState()
  requests = []
  respond = () => new Response('[]', { status: 200 })
  globalThis.fetch = async (input, init = {}) => {
    const url = new URL(String(input))
    requests.push({
      method: init.method ?? 'GET',
      path: url.pathname,
      auth: init.headers?.Authorization,
      body: init.body ? JSON.parse(init.body) : undefined,
    })
    return respond(init.method ?? 'GET', url.pathname)
  }
})

function signIn({ consent = true } = {}) {
  topics.loadTopicState({
    id: USER, analyticsConsent: consent, consentUpdatedAt: null,
    onboardingCompleted: true, preferences: { liked: [], disliked: [] }, language: 'en',
  })
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0))
const writes = () => requests.filter((request) => request.method !== 'GET')

// ---------- Who is tracked ----------

test('signed out, a reaction is not stored and nothing is sent', async () => {
  assert.equal(await engagement.setReaction(STORY, 'like'), false)
  assert.equal(engagement.readReaction(STORY), null)
  assert.deepEqual(requests, [])
})

test('without analytics consent nothing is sent either', async () => {
  signIn({ consent: false })
  assert.equal(await engagement.setReaction(STORY, 'like'), false)
  assert.equal(await engagement.logEvent(STORY, 'share'), false)
  await settle()
  assert.deepEqual(requests, [])
})

// ---------- Reactions ----------

test('signing in loads the user\'s reactions, so a liked heart is filled again', async () => {
  respond = (method, path) => path === `/users/${USER}/reactions`
    ? Response.json([{ story_id: STORY, reaction: 'like', updated_at: '2026-11-20T08:00:00Z' }])
    : new Response('[]')
  const stop = engagement.subscribeReactions(() => {})
  signIn()
  await settle()
  stop()
  assert.equal(requests[0].method, 'GET')
  assert.equal(requests[0].path, `/users/${USER}/reactions`)
  assert.equal(requests[0].auth, 'Bearer token')
  assert.equal(engagement.readReaction(STORY), 'like')
  assert.equal(engagement.readReaction(OTHER), null)
})

test('like is shown straight away and stored with PUT', async () => {
  signIn()
  const saving = engagement.setReaction(STORY, 'like')
  assert.equal(engagement.readReaction(STORY), 'like')
  assert.equal(await saving, true)
  assert.deepEqual(writes(), [{
    method: 'PUT', path: `/users/${USER}/reactions/${STORY}`, auth: 'Bearer token', body: { reaction: 'like' },
  }])
})

test('tapping like again removes it with DELETE', async () => {
  signIn()
  await engagement.setReaction(STORY, 'like')
  respond = () => new Response(null, { status: 204 })
  assert.equal(await engagement.setReaction(STORY, null), true)
  assert.equal(engagement.readReaction(STORY), null)
  assert.deepEqual(writes().map((request) => request.method), ['PUT', 'DELETE'])
})

test('"Not interested" is stored as a dislike', async () => {
  signIn()
  await engagement.setReaction(STORY, 'dislike')
  assert.deepEqual(writes()[0].body, { reaction: 'dislike' })
})

test('if storing fails, the button goes back to what the backend has', async () => {
  signIn()
  respond = (method) => method === 'GET' ? new Response('[]') : new Response('nope', { status: 500 })
  assert.equal(await engagement.setReaction(STORY, 'like'), false)
  assert.equal(engagement.readReaction(STORY), null)
})

test('quick taps are sent one at a time and end on the last choice', async () => {
  signIn()
  respond = (method) => new Response(method === 'DELETE' ? null : '{}', { status: method === 'DELETE' ? 204 : 200 })
  const first = engagement.setReaction(STORY, 'like')
  const second = engagement.setReaction(STORY, null)
  const third = engagement.setReaction(STORY, 'like')
  await Promise.all([first, second, third])
  assert.equal(engagement.readReaction(STORY), 'like')
  // The last two cancel out while the first is still on its way, so only what's needed is sent.
  const sent = writes()
  assert.equal(sent.at(-1)?.method, 'PUT')
  assert.ok(sent.length <= 3)
})

test('signing out forgets the reactions', async () => {
  signIn()
  await engagement.setReaction(STORY, 'like')
  topics.clearTopicState()
  assert.equal(engagement.readReaction(STORY), null)
})

// ---------- Events ----------

test('a share is sent as a share event for the story', async () => {
  signIn()
  assert.equal(await engagement.logEvent(STORY, 'share', { method: 'copy_link' }), true)
  const [event] = writes()
  assert.equal(event.method, 'POST')
  assert.equal(event.path, `/users/${USER}/events`)
  assert.equal(event.body.event_type, 'share')
  assert.equal(event.body.story_id, STORY)
  assert.deepEqual(event.body.metadata, { method: 'copy_link' })
  assert.match(event.body.session_id, /^[0-9a-f-]{36}$/)
  assert.ok(!Number.isNaN(Date.parse(event.body.occurred_at)))
})

test('a failed event never throws (tracking must not break sharing)', async () => {
  signIn()
  respond = () => new Response('Event type not found', { status: 404 })
  assert.equal(await engagement.logEvent(STORY, 'share'), false)
})

test('a story counts as read once, however often the reader swipes back and forth', async () => {
  signIn()
  engagement.logReadComplete(OTHER, 2, 4)
  engagement.logReadComplete(OTHER, 3, 4)
  engagement.logReadComplete(OTHER, 2, 4)
  await settle()
  const reads = writes().filter((request) => request.body.event_type === 'read_complete')
  assert.equal(reads.length, 1)
  assert.equal(reads[0].body.story_id, OTHER)
  assert.deepEqual(reads[0].body.metadata, { part: 2, parts: 4 })
})

test('a read the backend refused is tried again on the next swipe', async () => {
  signIn()
  const story = '44444444-4444-4444-8444-444444444444'
  respond = (method) => method === 'POST' ? new Response('Event type not found', { status: 404 }) : new Response('[]')
  engagement.logReadComplete(story, 2, 4)
  await settle()
  respond = () => new Response('{}', { status: 201 })
  engagement.logReadComplete(story, 3, 4)
  await settle()
  const reads = writes().filter((request) => request.body.event_type === 'read_complete' && request.body.story_id === story)
  assert.equal(reads.length, 2)
})
