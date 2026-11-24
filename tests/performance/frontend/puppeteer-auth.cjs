/* Inject the Playwright storage_state produced by the existing E2E login fixture.
 * LHCI calls this script before each URL group. The storage state origin must
 * match LHCI_BASE_URL exactly (same scheme, hostname and port).
 */
const fs = require('node:fs')

module.exports = async (browser, context) => {
  const statePath = process.env.LHCI_AUTH_STATE
  if (!statePath) throw new Error('LHCI_AUTH_STATE is not set')

  const state = JSON.parse(fs.readFileSync(statePath, 'utf8'))
  const target = new URL(context.url)
  const page = await browser.newPage()

  try {
    const cookies = (state.cookies || [])
      .filter((cookie) => cookie.expires === -1 || !cookie.expires || cookie.expires > Date.now() / 1000)
      .map((cookie) => {
        const result = {
          name: cookie.name,
          value: cookie.value,
          domain: cookie.domain,
          path: cookie.path || '/',
          secure: Boolean(cookie.secure),
          httpOnly: Boolean(cookie.httpOnly),
        }
        if (cookie.expires && cookie.expires > 0) result.expires = cookie.expires
        if (cookie.sameSite) result.sameSite = cookie.sameSite
        return result
      })

    if (cookies.length) await page.setCookie(...cookies)

    // localStorage is origin-scoped. Only copy entries matching the audit origin.
    const originState = (state.origins || []).find(
      (entry) => entry.origin === target.origin,
    )
    await page.goto(target.origin, { waitUntil: 'domcontentloaded' })
    if (originState && originState.localStorage) {
      await page.evaluate((entries) => {
        for (const item of entries) localStorage.setItem(item.name, item.value)
      }, originState.localStorage)
    }
  } finally {
    await page.close()
  }
}
