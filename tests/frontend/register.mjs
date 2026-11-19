// Loaded with `node --import` before the frontend tests run.
import { register } from 'node:module'

register('./resolve-from-frontend.mjs', import.meta.url)
