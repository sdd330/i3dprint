import { refreshSessionForRender } from '../utils/session'

const skipped = ['/api/', '/oauth/', '/_nuxt/', '/__nuxt']

export default defineEventHandler(async (event) => {
  if (event.method !== 'GET') return
  const path = event.path.split('?')[0] ?? '/'
  if (path === '/login' || skipped.some((prefix) => path.startsWith(prefix))) return
  await refreshSessionForRender(event)
})
