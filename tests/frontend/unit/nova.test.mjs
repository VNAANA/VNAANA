import assert from 'node:assert/strict'
import { after, afterEach, before, mock, test } from 'node:test'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

const frontendRoot = fileURLToPath(new URL('../../../Frontend', import.meta.url))
const storyId = '7d5f2f9e-3a1b-4c2d-9e8f-0a1b2c3d4e5f'
let server, nova

// Load the application's actual TypeScript module.
before(async () => {
  server = await createServer({
    root: frontendRoot, configFile: false, envFile: false, logLevel: 'silent',
    server: { middlewareMode: true, hmr: false, watch: null },
    define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://api.test') },
  })
  nova = await server.ssrLoadModule('/src/utils/nova.ts')
})

after(async () => { await server?.close() })
afterEach(() => { mock.restoreAll() })

// Mirrors the backend's json.dumps(history, ensure_ascii=False) size check.
const pythonJsonBytes = (history) => Buffer.byteLength(
  '[' + history.map((m) => `{"role": ${JSON.stringify(m.role)}, "content": ${JSON.stringify(m.content)}}`).join(', ') + ']',
)

const answered = { text: 'The library opened on Monday.', sources: ['https://nos.nl/a'], uncertainty: 'Text from 1 of 1.', status: 'answered' }

test('toHistory keeps the last two exchanges, oldest first', () => {
  const history = nova.toHistory([
    { question: 'q1', answer: 'a1' },
    { question: 'q2', answer: 'a2' },
    { question: 'q3', answer: 'a3' },
  ])
  assert.deepEqual(history, [
    { role: 'user', content: 'q2' },
    { role: 'assistant', content: 'a2' },
    { role: 'user', content: 'q3' },
    { role: 'assistant', content: 'a3' },
  ])
})

test('toHistory clips long answers and stays under the byte limit', () => {
  const long = 'é'.repeat(900)
  const history = nova.toHistory([
    { question: 'first?', answer: long },
    { question: 'second?', answer: long },
  ])
  assert.ok(history.every((m) => [...m.content].length <= 500))
  assert.ok(pythonJsonBytes(history) <= 2000, `history is ${pythonJsonBytes(history)} bytes`)
  // 'é' is 2 bytes, so only the newest exchange fits.
  assert.deepEqual(history.map((m) => m.role), ['user', 'assistant'])
  assert.equal(history[0].content, 'second?')
})

test('toHistory leaves out exchanges with a blank message', () => {
  assert.deepEqual(nova.toHistory([{ question: 'q', answer: '  ' }]), [])
})

test('askNova posts the question, language and history to the story endpoint', async () => {
  const fetchMock = mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(answered), { status: 200 }))
  const answer = await nova.askNova(storyId, 'When?', 'en', [{ question: 'What happened?', answer: 'A library opened.' }])

  assert.deepEqual(answer, answered)
  const [url, init] = fetchMock.mock.calls[0].arguments
  assert.match(String(url), new RegExp(`/ai/stories/${storyId}/ask$`))
  assert.equal(init.method, 'POST')
  assert.deepEqual(JSON.parse(init.body), {
    question: 'When?',
    language: 'en',
    history: [
      { role: 'user', content: 'What happened?' },
      { role: 'assistant', content: 'A library opened.' },
    ],
  })
})

test('askNova maps HTTP errors to chat error codes', async () => {
  for (const [status, code] of [[404, 'notFound'], [422, 'invalidRequest'], [503, 'modelUnavailable'], [500, 'failed']]) {
    mock.method(globalThis, 'fetch', async () => new Response('{}', { status }))
    await assert.rejects(nova.askNova(storyId, 'q', 'nl'), (error) => error.code === code)
    mock.restoreAll()
  }
})

test('askNova rejects a response with the wrong shape', async () => {
  mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ ...answered, status: 'conflicting' }), { status: 200 }))
  await assert.rejects(nova.askNova(storyId, 'q', 'en'), (error) => error.code === 'invalidResponse')
})
