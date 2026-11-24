const path = require('node:path')

const baseUrl = process.env.LHCI_BASE_URL || 'http://localhost:5173'
const authState = process.env.LHCI_AUTH_STATE

const publicUrls = [`${baseUrl}/#login`, `${baseUrl}/#sign-up`]
const authenticatedUrls = [
  `${baseUrl}/`,
  `${baseUrl}/#explore`,
  `${baseUrl}/#profile`,
  `${baseUrl}/#profile?tab=topics`,
]

if (authenticatedUrls.length && !authState) {
  throw new Error(
    'LHCI_AUTH_STATE must point to a Playwright storage_state JSON file for protected routes.',
  )
}

module.exports = {
  ci: {
    collect: {
      // The backend must already be running and Vite must serve the production build.
      startServerCommand:
        'pnpm preview --host localhost --port 5173 --strictPort',
      startServerReadyPattern: '5173',
      startServerReadyTimeout: 60000,
      url: [...publicUrls, ...authenticatedUrls],
      numberOfRuns: 1,
      puppeteerScript: '../tests/performance/frontend/puppeteer-auth.cjs',
      settings: {
        disableStorageReset: true,
        maxWaitForLoad: 90000,
      },
    },
    assert: {
      assertions: {
        'categories:performance': ['warn', { minScore: 0.8 }],
        'first-contentful-paint': ['warn', { maxNumericValue: 1800 }],
        'largest-contentful-paint': ['warn', { maxNumericValue: 2500 }],
        'total-blocking-time': ['warn', { maxNumericValue: 200 }],
        'cumulative-layout-shift': ['warn', { maxNumericValue: 0.1 }],
      },
    },
    upload: {
      target: 'filesystem',
      outputDir: path.resolve(__dirname, '../../../.lighthouseci'),
    },
  },
}
