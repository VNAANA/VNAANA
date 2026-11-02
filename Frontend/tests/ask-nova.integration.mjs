import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'


const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// articleToStory uses the browser DOMParser to normalize RSS descriptions.
globalThis.DOMParser = class {
  parseFromString(value) {
    const text = value
      .replace(/<[^>]*>/g, ' ')
      .replace(/&amp;/g, '&')
      .replace(/\s+/g, ' ')
      .trim()
    return { body: { textContent: text } }
  }
}

const server = await createServer({
  root: frontendRoot,
  appType: 'custom',
  envFile: false,
  optimizeDeps: { noDiscovery: true },
  define: {
    'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://localhost:8000'),
  },
  server: { middlewareMode: true },
})

try {
  const { articleToStory } = await server.ssrLoadModule('/src/utils/articles.ts')
  const { askNova, simplifyNova } = await server.ssrLoadModule('/src/utils/nova.ts')
  const { NovaChatLog } = await server.ssrLoadModule('/src/components/FeedPost/NovaChat.tsx')
  const { PostContext } = await server.ssrLoadModule('/src/components/FeedPost/PostContext.ts')

  const baseArticle = {
    id: 'article-1',
    provider: { name: 'Test News', domain: 'example.test', reliability_status: 'verified' },
    canonical_url: 'https://example.test/article-1',
    title: 'A complete headline',
    description: '<p>An unshortened description with supporting information.</p>',
    author: null,
    published_at: null,
    first_seen_at: '2026-11-02T12:00:00Z',
  }

  const fullText = 'The exact full article text.\nA second paragraph.'
  const fullStory = articleToStory({ ...baseArticle, content: fullText })
  assert.equal(fullStory.novaArticle.groundingMode, 'full_article')
  assert.equal(fullStory.novaArticle.groundingText, fullText)

  const previewStory = articleToStory({ ...baseArticle, id: 'article-2', content: null })
  assert.equal(previewStory.novaArticle.groundingMode, 'preview')
  assert.equal(previewStory.novaArticle.previewIncludesDescription, true)
  assert.equal(
    previewStory.novaArticle.groundingText,
    'A complete headline\n\nAn unshortened description with supporting information.',
  )

  const headlineStory = articleToStory({ ...baseArticle, id: 'article-3', description: null, content: null })
  assert.equal(headlineStory.novaArticle.groundingText, 'A complete headline')
  assert.equal(headlineStory.novaArticle.previewIncludesDescription, false)

  const requests = []
  globalThis.fetch = async (url, options) => {
    requests.push({ url: String(url), body: JSON.parse(options.body) })
    return new Response(JSON.stringify({
      text: 'Grounded response.',
      sources: ['https://example.test/article-1'],
      uncertainty: 'Only supplied context was checked.',
      status: 'answered',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }

  await askNova(previewStory.novaArticle, 'What happened?', 'en')
  await simplifyNova(previewStory.novaArticle, 'nl')
  assert.equal(new URL(requests[0].url).pathname, '/ai/ask')
  assert.equal(requests[0].body.question, 'What happened?')
  assert.equal(requests[0].body.article_text, previewStory.novaArticle.groundingText)
  assert.equal(new URL(requests[1].url).pathname, '/ai/summarize')
  assert.equal('question' in requests[1].body, false)
  assert.equal(requests[1].body.language, 'nl')

  const answer = {
    text: 'A preview-grounded response.',
    sources: [],
    uncertainty: 'Only supplied context was checked.',
    status: 'answered',
  }
  const chat = {
    messages: [{ id: 1, from: 'nova', answer }],
    pending: false,
    send: async () => {},
    sendSuggestion: async () => {},
    language: 'en',
    setLanguage: () => {},
    available: true,
    tooLong: false,
    groundingMode: 'preview',
    previewIncludesDescription: true,
  }
  const context = {
    story: previewStory,
    carousel: {},
    actions: {},
    chat,
    composerFocusRequest: 0,
    titleId: 'title',
    partIds: [],
    partLabels: [],
  }
  const html = renderToStaticMarkup(
    React.createElement(PostContext.Provider, { value: context }, React.createElement(NovaChatLog)),
  )
  assert.match(html, /Full article text is unavailable/)
  assert.match(html, /headline and available description/)
  assert.match(html, /A preview-grounded response/)

  const headlineHtml = renderToStaticMarkup(
    React.createElement(
      PostContext.Provider,
      { value: { ...context, story: headlineStory, chat: { ...chat, previewIncludesDescription: false } } },
      React.createElement(NovaChatLog),
    ),
  )
  assert.match(headlineHtml, /Nova is using only the headline\./)

  console.log('Ask Nova frontend integration checks passed.')
} finally {
  await server.close()
}
