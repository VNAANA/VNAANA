// The tests live outside Frontend/, so Node can't find packages like `vite`
// on its own. When a package isn't found from the test file, look it up from
// Frontend/ instead, so the tests always use the same versions as the app.
const frontend = new URL('../../Frontend/package.json', import.meta.url).href

export async function resolve(specifier, context, next) {
  try {
    return await next(specifier, context)
  } catch (error) {
    if (error?.code !== 'ERR_MODULE_NOT_FOUND') throw error
    try {
      return await next(specifier, { ...context, parentURL: frontend })
    } catch {
      // Not in Frontend/ either: show the original error, which names the test file.
      throw error
    }
  }
}
