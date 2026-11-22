import type { H3Event } from 'h3'
import { createError, deleteCookie, getCookie, setCookie } from 'h3'
import { isStaff, revokeTokens, rotateRefreshToken, userByAccessToken, type IssuedTokens, type SessionUser } from './oauth'

const ACCESS_COOKIE = 'vz_access'
const REFRESH_COOKIE = 'vz_refresh'

function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    sameSite: 'lax' as const,
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge,
  }
}

export function setSessionCookies(event: H3Event, tokens: IssuedTokens) {
  setCookie(event, ACCESS_COOKIE, tokens.accessToken, cookieOptions(tokens.expiresIn))
  setCookie(event, REFRESH_COOKIE, tokens.refreshToken, cookieOptions(14 * 24 * 60 * 60))
}

export function clearPkceCookies(event: H3Event) {
  deleteCookie(event, 'vz_verifier', { path: '/' })
  deleteCookie(event, 'vz_state', { path: '/' })
  deleteCookie(event, 'vz_next', { path: '/' })
}

export function clearSessionCookies(event: H3Event) {
  deleteCookie(event, ACCESS_COOKIE, { path: '/' })
  deleteCookie(event, REFRESH_COOKIE, { path: '/' })
  clearPkceCookies(event)
}

export async function requireUser(event: H3Event) {
  const access = getCookie(event, ACCESS_COOKIE)
  if (access) {
    const user = await userByAccessToken(access)
    if (user) return user
  }
  const refresh = getCookie(event, REFRESH_COOKIE)
  if (refresh) {
    const rotated = await rotateRefreshToken(refresh)
    if (rotated) {
      setSessionCookies(event, rotated)
      return rotated.user
    }
  }
  throw createError({ statusCode: 401, statusMessage: '未登录' })
}

export async function requireStaff(event: H3Event) {
  const user = await requireUser(event)
  if (!isStaff(user)) throw createError({ statusCode: 403, statusMessage: '需要负责人权限' })
  return user
}

export function toPublicUser(user: SessionUser) {
  return { code: user.code, name: user.name, role: user.role, admin: isStaff(user) }
}

export async function logout(event: H3Event) {
  await revokeTokens(getCookie(event, ACCESS_COOKIE), getCookie(event, REFRESH_COOKIE))
  clearSessionCookies(event)
}
