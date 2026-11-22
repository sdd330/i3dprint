import { getCookie, getQuery, getRequestURL, setCookie } from 'h3'
import { randomToken, safeNext } from '../utils/oauth'

export default defineEventHandler((event) => {
  const url = getRequestURL(event)
  if (url.pathname !== '/login') return
  const options = {
    httpOnly: true,
    sameSite: 'lax' as const,
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: 600,
  }
  if (!getCookie(event, 'vz_verifier') || !getCookie(event, 'vz_state')) {
    setCookie(event, 'vz_verifier', randomToken(), options)
    setCookie(event, 'vz_state', randomToken(16), options)
  }
  const next = getQuery(event).next
  if (typeof next === 'string') setCookie(event, 'vz_next', safeNext(next), options)
})
