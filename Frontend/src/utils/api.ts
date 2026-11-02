/** Full URL for a backend path, e.g. apiUrl('/articles/random'). */
export function apiUrl(path: string) {
  const base = import.meta.env.VITE_API_BASE_URL?.trim()
  if (!base) throw new Error('Missing API URL')
  return `${base.replace(/\/$/, '')}${path}`
}
