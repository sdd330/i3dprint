import { getCookie, getQuery, getRequestURL, sendRedirect } from 'h3'
import { exchangeAuthorizationCode, safeNext } from '../../utils/oauth'
import { clearPkceCookies, setSessionCookies } from '../../utils/session'

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const code = typeof query.code === 'string' ? query.code : ''
  const state = typeof query.state === 'string' ? query.state : ''
  const expected = getCookie(event, 'vz_state')
  const verifier = getCookie(event, 'vz_verifier')
  if (!code || !state || !expected || state !== expected || !verifier) {
    return sendRedirect(event, '/login?error=expired', 303)
  }
  const redirectUri = new URL('/oauth/callback', getRequestURL(event).origin).toString()
  try {
    const tokens = await exchangeAuthorizationCode({ code, verifier, redirectUri })
    setSessionCookies(event, tokens)
    const next = safeNext(getCookie(event, 'vz_next'))
    clearPkceCookies(event)
    return sendRedirect(event, next, 303)
  } catch {
    clearPkceCookies(event)
    return sendRedirect(event, '/login?error=1', 303)
  }
})
