import assert from 'node:assert/strict'
import { after, before, beforeEach, mock, test } from 'node:test'
import { createServer } from 'vite'
import { createClient } from '@supabase/supabase-js'

const origin = 'http://localhost:5173'
const owner = 'bc23ace9-2ba8-46f2-b98b-12230f22eb3a'
const other = 'ed916111-d043-472c-b9a7-1c7cb799e17e'
let server, account, google, link, sdk

// Load the application's actual TypeScript modules with a controlled Auth client.
before(async () => {
  server = await createServer({
    configFile: false, envFile: false, logLevel: 'silent',
    server: { middlewareMode: true, hmr: false, watch: null },
    plugins: [{
      name: 'auth-test-double', enforce: 'pre',
      resolveId(id) { if (id === './supabase') return '\0vna-auth-test-client' },
      load(id) {
        if (id === '\0vna-auth-test-client') return 'export const supabase = { get auth() { return globalThis.testAuth } }'
      },
    }],
  })
  account = await server.ssrLoadModule('/src/utils/accountAuth.ts')
  google = await server.ssrLoadModule('/src/utils/googleSignIn.ts')
  link = await server.ssrLoadModule('/src/utils/googleLink.ts')
})

beforeEach(() => {
  const items = new Map()
  globalThis.window = { location: { origin }, sessionStorage: {
    getItem: key => items.get(key) ?? null, setItem: (key, value) => items.set(key, value),
    removeItem: key => items.delete(key),
  } }
  sdk = globalThis.testAuth = {
    getUser: mock.fn(async () => ({ data: { user: { id: owner, identities: [] } } })),
    getSession: mock.fn(async () => ({ data: { session: { user: { id: owner } } } })),
    signUp: mock.fn(), signInWithPassword: mock.fn(), updateUser: mock.fn(),
    signInWithOAuth: mock.fn(async () => ({ error: null })),
    linkIdentity: mock.fn(async () => ({ error: null })),
  }
})
after(async () => {
  await server?.close()
  delete globalThis.window
  delete globalThis.testAuth
})

test('email registration awaiting verification never links an identity or sets an existing password', async () => {
  sdk.signUp.mock.mockImplementation(async () => ({ data: { session: null }, error: null }))
  const result = await account.registerWithPassword({ email: ' reader@example.com ', password: 'test-password',
    firstName: 'A', lastName: 'Reader', language: 'en', consent: true })
  assert.equal(result.data.session, null)
  assert.equal(sdk.signUp.mock.calls[0].arguments[0].email, 'reader@example.com')
  assert.equal(sdk.linkIdentity.mock.callCount(), 0)
  assert.equal(sdk.updateUser.mock.callCount(), 0)
})

test('both new and previously verified email users start Google OAuth through Supabase', async () => {
  assert.equal(await google.startGoogleSignIn(), true)
  assert.equal(sdk.signInWithOAuth.mock.calls[0].arguments[0].provider, 'google')
  assert.equal(sdk.signUp.mock.callCount(), 0)
  assert.equal(sdk.linkIdentity.mock.callCount(), 0)
})

test('Google user adds a password to their verified account and can submit a password login', async () => {
  await account.setAccountPassword(owner, 'test-password', 'verification-code')
  assert.deepEqual(sdk.updateUser.mock.calls[0].arguments, [{ password: 'test-password', nonce: 'verification-code' }])
  await account.loginWithPassword('reader@example.com', 'test-password')
  assert.deepEqual(sdk.signInWithPassword.mock.calls[0].arguments, [{ email: 'reader@example.com', password: 'test-password' }])
  assert.equal(sdk.signUp.mock.callCount(), 0)
})

test('Profile derives Google status from verified identities regardless of last provider', async () => {
  for (const [lastProvider, identities, status] of [
    ['email', [{ provider: 'email' }, { provider: 'google' }], 'connected'],
    ['google', [{ provider: 'google' }], 'connected'],
    ['google', [{ provider: 'email' }], 'disconnected'],
    ['google', undefined, 'unavailable'],
  ]) {
    sdk.getUser.mock.mockImplementation(async () => ({ data: { user: {
      id: owner, identities, app_metadata: { provider: lastProvider },
    } } }))
    assert.equal(await account.readGoogleStatus(owner), status)
  }
  // Opening settings is enough to check a Google-only account; password setup is opt-in.
  assert.equal(sdk.updateUser.mock.callCount(), 0)
  assert.equal(sdk.linkIdentity.mock.callCount(), 0)
})

test('failed identity verification never offers a new Google link', async () => {
  for (const response of [{ data: { user: null }, error: { code: 'session_expired' } },
    { data: { user: { id: other, identities: [] } } }]) {
    sdk.getUser.mock.mockImplementation(async () => response)
    assert.equal(await account.readGoogleStatus(owner), 'unavailable')
    assert.equal(await link.startGoogleLink(owner), 'failed')
  }
  assert.equal(sdk.linkIdentity.mock.callCount(), 0)
})

test('expired or switched session cannot attach a password or start Google linking', async () => {
  for (const user of [null, { id: other }]) {
    sdk.getUser.mock.mockImplementation(async () => ({ data: { user } }))
    await assert.rejects(account.setAccountPassword(owner, 'test-password'))
    assert.equal(await link.startGoogleLink(owner), 'failed')
  }
  assert.equal(sdk.updateUser.mock.callCount(), 0)
  assert.equal(sdk.linkIdentity.mock.callCount(), 0)
})

test('password changes send the current password to Supabase, including on a verification retry', async () => {
  await account.setAccountPassword(owner, 'next-password', 'verification-code', 'current-password')
  assert.deepEqual(sdk.updateUser.mock.calls[0].arguments, [{
    password: 'next-password', current_password: 'current-password', nonce: 'verification-code',
  }])
})

test('settings link finishes only after the original account has a verified Google identity', async () => {
  assert.equal(await link.startGoogleLink(owner), null)
  const options = sdk.linkIdentity.mock.calls[0].arguments[0]
  assert.equal(options.provider, 'google')
  const callback = link.readLinkCallback(new URL(options.options.redirectTo + '&code=test'))
  sdk.getUser.mock.mockImplementation(async () => ({ data: { user: { id: owner, identities: [{ provider: 'google' }] } } }))
  assert.equal(await link.finishGoogleLink(callback), 'linked')
  assert.equal(link.readLinkCallback(new URL(options.options.redirectTo)).subject, null)
  assert.equal(link.readLinkCallback(new URL(origin + '/?code=ordinary-login')), null)
})

test('callback rejects a different UID and an account with no linked Google identity', async () => {
  assert.equal(await link.finishGoogleLink({ subject: other, error: null }), 'failed')
  assert.equal(await link.finishGoogleLink({ subject: owner, error: null }), 'failed')
})

test('conflicting Google identities and disabled manual linking return actionable errors', async () => {
  for (const [code, expected] of [['identity_already_exists', 'conflict'], ['manual_linking_disabled', 'disabled']]) {
    sdk.linkIdentity.mock.mockImplementation(async () => ({ error: { code } }))
    assert.equal(await link.startGoogleLink(owner), expected)
    const url = new URL(origin + '/?auth_flow=link-google#error=access_denied&error_code=' + code)
    assert.equal(await link.finishGoogleLink(link.readLinkCallback(url)), expected)
  }
  assert.equal(sdk.updateUser.mock.callCount(), 0)
  assert.equal(sdk.signUp.mock.callCount(), 0)
})

test('Supabase restores a stored session and local logout clears it', async () => {
  const key = 'vna-test-session'
  const claims = { sub: owner, exp: Math.floor(Date.now() / 1000) + 3600 }
  const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url')
  const token = [encode({ alg: 'HS256', typ: 'JWT' }), encode(claims), 'dGVzdA'].join('.')
  const store = new Map([[key, JSON.stringify({ access_token: token, refresh_token: 'test-refresh',
    expires_at: claims.exp, token_type: 'bearer', user: { id: owner } })]])
  const client = createClient('https://example.supabase.co', 'public-test-key', {
    auth: { storageKey: key, persistSession: true, autoRefreshToken: false, detectSessionInUrl: false,
      storage: { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: k => store.delete(k) } },
    global: { fetch: async () => new Response(null, { status: 204 }) },
  })
  assert.equal((await client.auth.getSession()).data.session.user.id, owner)
  assert.equal((await client.auth.signOut({ scope: 'local' })).error, null)
  assert.equal((await client.auth.getSession()).data.session, null)
})
