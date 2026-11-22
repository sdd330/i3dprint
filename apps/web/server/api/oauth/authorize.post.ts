import { getCookie, getRequestIP, getRequestURL, readBody, sendRedirect } from 'h3'
import {
  assertLoginAllowed,
  authenticate,
  clearLoginFailure,
  issueAuthorizationCode,
  recordLoginFailure,
} from '../../utils/oauth'

export default defineEventHandler(async (event) => {
  const body = await readBody<{ username?: string; password?: string }>(event)
  const username = String(body?.username ?? '').trim()
  const password = String(body?.password ?? '')
  const verifier = getCookie(event, 'vz_verifier')
  const state = getCookie(event, 'vz_state')
  const ip = getRequestIP(event, { xForwardedFor: true }) ?? 'unknown'
  const limitKey = `${ip}:${username}`
  if (!verifier || !state) {
    return sendRedirect(event, '/login?error=expired', 303)
  }
  try {
    assertLoginAllowed(limitKey)
  } catch {
    return sendRedirect(event, '/login?error=locked', 303)
  }
  const user = username && password ? await authenticate(username, password) : null
  if (!user) {
    recordLoginFailure(limitKey)
    return sendRedirect(event, '/login?error=1', 303)
  }
  clearLoginFailure(limitKey)
  const redirectUri = new URL('/oauth/callback', getRequestURL(event).origin).toString()
  const code = await issueAuthorizationCode({ userId: user.id, verifier, redirectUri })
  const location = new URL('/oauth/callback', getRequestURL(event).origin)
  location.searchParams.set('code', code)
  location.searchParams.set('state', state)
  return sendRedirect(event, location.toString(), 303)
})
