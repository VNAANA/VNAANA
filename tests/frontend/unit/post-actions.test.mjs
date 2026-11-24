import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

/* Which post buttons need an account. Signed out, only Share (and Ask Nova) are offered. */

const frontendRoot = fileURLToPath(new URL('../../../Frontend', import.meta.url))
let server, reactionBar

before(async () => {
  server = await createServer({
    root: frontendRoot, configFile: false, envFile: false, logLevel: 'silent',
    server: { middlewareMode: true, hmr: false, watch: null },
    define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://api.test') },
    plugins: [{
      name: 'supabase-stub', enforce: 'pre',
      resolveId(id) { if (id.endsWith('/supabase') || id === './supabase') return '\0supabase-stub' },
      load(id) { if (id === '\0supabase-stub') return 'export const supabase = {}' },
    }],
  })
  reactionBar = await server.ssrLoadModule('/src/components/FeedPost/accountActions.ts')
})

after(async () => { await server?.close() })

test('like, dislike, not interested and save need an account', () => {
  for (const kind of ['like', 'dislike', 'notInterested', 'save']) {
    assert.ok(reactionBar.ACCOUNT_ACTIONS.includes(kind), `${kind} should need an account`)
  }
})

test('share works without an account', () => {
  assert.equal(reactionBar.ACCOUNT_ACTIONS.includes('share'), false)
})
