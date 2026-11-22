import { createHash, randomBytes, timingSafeEqual } from 'node:crypto'
import type { PoolConnection, RowDataPacket } from 'mysql2/promise'
import { createError } from 'h3'
import { getDb, queryRows, withTx } from './db'
import { verifyPassword } from './password'

export const OAUTH_CLIENT = 'violet-z'
export const OAUTH_SCOPE = 'openid profile'
const ACCESS_SECONDS = 15 * 60
const REFRESH_SECONDS = 14 * 24 * 60 * 60

interface UserRow extends RowDataPacket {
  id: number
  code: string
  name: string
  role: string
  password_hash: string
  is_active: number
}

interface CodeRow extends RowDataPacket {
  id: number
  user_id: number
  client_id: number
  redirect_uri: string
  code_challenge: string
  scope: string
  expires_at: string
  consumed: number
}

interface TokenRow extends RowDataPacket {
  id: number
  user_id: number
  code: string
  name: string
  role: string
  access_expires: string
  refresh_expires: string
  scope: string
}

export interface SessionUser {
  id: number
  code: string
  name: string
  role: string
}

export function isStaff(user: SessionUser) {
  return user.role === 'root' || user.role === 'admin'
}

export interface IssuedTokens {
  accessToken: string
  refreshToken: string
  expiresIn: number
  scope: string
  user: SessionUser
}

const failures = new Map<string, { count: number; resetAt: number }>()

export function randomToken(bytes = 32) {
  return randomBytes(bytes).toString('base64url')
}

export function sha256(value: string) {
  return createHash('sha256').update(value).digest('hex')
}

export function pkceChallenge(verifier: string) {
  return createHash('sha256').update(verifier).digest('base64url')
}

export function safeNext(value: string | undefined | null) {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/login')) return '/'
  return value
}

export function assertLoginAllowed(key: string) {
  const now = Date.now()
  const current = failures.get(key)
  if (current && current.resetAt > now && current.count >= 8) {
    throw createError({ statusCode: 429, statusMessage: '尝试过多，请稍后再来' })
  }
}

export function recordLoginFailure(key: string) {
  const now = Date.now()
  const current = failures.get(key)
  if (!current || current.resetAt <= now) {
    failures.set(key, { count: 1, resetAt: now + 10 * 60 * 1000 })
    return
  }
  current.count += 1
}

export function clearLoginFailure(key: string) {
  failures.delete(key)
}

export async function authenticate(username: string, password: string) {
  const rows = await queryRows<UserRow>(
    `SELECT u.id, u.sys_user_code AS code, u.name, r.sys_role_code AS role, u.password_hash, u.is_active
     FROM t_sys_user u
     JOIN t_sys_role r ON r.id = u.role_id
     WHERE u.valid = 1 AND u.sys_user_code = ? LIMIT 1`,
    [username],
  )
  const user = rows[0]
  if (!user || user.is_active !== 1) return null
  const matched = await verifyPassword(password, user.password_hash)
  if (!matched) return null
  return { id: Number(user.id), code: user.code, name: user.name, role: user.role }
}

export async function issueAuthorizationCode(input: {
  userId: number
  verifier: string
  redirectUri: string
}) {
  const code = randomToken()
  const businessCode = randomToken(12).slice(0, 32)
  await withTx(async (conn) => {
    const clientId = await clientIdOf(conn)
    await conn.query(
      `INSERT INTO t_sys_oauth_code
        (sys_oauth_code_code, code_hash, client_id, user_id, redirect_uri, code_challenge, scope, expires_at, consumed, create_user_code)
       VALUES (?, ?, ?, ?, ?, ?, ?, DATE_ADD(UTC_TIMESTAMP(), INTERVAL 2 MINUTE), 0, 'oauth')`,
      [businessCode, sha256(code), clientId, input.userId, input.redirectUri, pkceChallenge(input.verifier), OAUTH_SCOPE],
    )
  })
  return code
}

export async function exchangeAuthorizationCode(input: {
  code: string
  verifier: string
  redirectUri: string
}) {
  return withTx(async (conn) => {
    const [rows] = await conn.query<CodeRow[]>(
      `SELECT id, user_id, client_id, redirect_uri, code_challenge, scope, expires_at, consumed
       FROM t_sys_oauth_code WHERE code_hash = ? AND valid = 1 LIMIT 1 FOR UPDATE`,
      [sha256(input.code)],
    )
    const row = rows[0]
    if (!row || row.consumed === 1) {
      throw createError({ statusCode: 400, statusMessage: '授权码无效' })
    }
    if (Date.parse(normalizeDate(row.expires_at)) <= Date.now()) {
      throw createError({ statusCode: 400, statusMessage: '授权码无效' })
    }
    if (!fixedEqual(row.redirect_uri, input.redirectUri) || !fixedEqual(row.code_challenge, pkceChallenge(input.verifier))) {
      throw createError({ statusCode: 400, statusMessage: '授权码无效' })
    }
    await conn.query(`UPDATE t_sys_oauth_code SET consumed = 1 WHERE id = ?`, [row.id])
    return insertToken(conn, Number(row.user_id), Number(row.client_id), row.scope)
  })
}

export async function rotateRefreshToken(refreshToken: string) {
  return withTx(async (conn) => {
    const [rows] = await conn.query<TokenRow[]>(
      `SELECT t.id, t.user_id, t.refresh_expires, t.scope, u.sys_user_code AS code, u.name, r.sys_role_code AS role
       FROM t_sys_oauth_token t
       JOIN t_sys_user u ON u.id = t.user_id
       JOIN t_sys_role r ON r.id = u.role_id
       WHERE t.refresh_hash = ? AND t.valid = 1 AND u.valid = 1 AND u.is_active = 1
       LIMIT 1 FOR UPDATE`,
      [sha256(refreshToken)],
    )
    const row = rows[0]
    if (!row || Date.parse(normalizeDate(row.refresh_expires)) <= Date.now()) return null
    await conn.query(`UPDATE t_sys_oauth_token SET valid = 0 WHERE id = ?`, [row.id])
    const clientId = await clientIdOf(conn)
    return insertToken(conn, Number(row.user_id), clientId, row.scope, {
      id: Number(row.user_id),
      code: row.code,
      name: row.name,
      role: row.role,
    })
  })
}

export async function userByAccessToken(accessToken: string) {
  const rows = await queryRows<TokenRow>(
    `SELECT t.user_id, t.access_expires, u.sys_user_code AS code, u.name, r.sys_role_code AS role
     FROM t_sys_oauth_token t
     JOIN t_sys_user u ON u.id = t.user_id
     JOIN t_sys_role r ON r.id = u.role_id
     WHERE t.access_hash = ? AND t.valid = 1 AND u.valid = 1 AND u.is_active = 1
     LIMIT 1`,
    [sha256(accessToken)],
  )
  const row = rows[0]
  if (!row || Date.parse(normalizeDate(row.access_expires)) <= Date.now()) return null
  return { id: Number(row.user_id), code: row.code, name: row.name, role: row.role }
}

export async function revokeTokens(accessToken?: string, refreshToken?: string) {
  const hashes = [accessToken, refreshToken].filter((item): item is string => Boolean(item)).map(sha256)
  if (hashes.length === 0) return
  const accessHash = hashes[0] ?? ''
  const refreshHash = hashes[1] ?? accessHash
  await getDb().query(
    `UPDATE t_sys_oauth_token SET valid = 0
     WHERE access_hash = ? OR refresh_hash = ? OR access_hash = ? OR refresh_hash = ?`,
    [accessHash, accessHash, refreshHash, refreshHash],
  )
}

async function insertToken(
  conn: PoolConnection,
  userId: number,
  clientId: number,
  scope: string,
  knownUser?: SessionUser,
): Promise<IssuedTokens> {
  const accessToken = randomToken()
  const refreshToken = randomToken()
  const businessCode = randomToken(12).slice(0, 32)
  await conn.query(
    `INSERT INTO t_sys_oauth_token
      (sys_oauth_token_code, user_id, client_id, access_hash, refresh_hash, scope, access_expires, refresh_expires, create_user_code)
     VALUES (?, ?, ?, ?, ?, ?, DATE_ADD(UTC_TIMESTAMP(), INTERVAL ? SECOND), DATE_ADD(UTC_TIMESTAMP(), INTERVAL ? SECOND), 'oauth')`,
    [businessCode, userId, clientId, sha256(accessToken), sha256(refreshToken), scope, ACCESS_SECONDS, REFRESH_SECONDS],
  )
  const user = knownUser ?? (await userOf(conn, userId))
  return { accessToken, refreshToken, expiresIn: ACCESS_SECONDS, scope, user }
}

async function clientIdOf(conn: PoolConnection) {
  const [rows] = await conn.query<RowDataPacket[]>(
    `SELECT id FROM t_sys_oauth_client WHERE valid = 1 AND sys_oauth_client_code = ? LIMIT 1`,
    [OAUTH_CLIENT],
  )
  const id = rows[0]?.id
  if (!id) throw createError({ statusCode: 500, statusMessage: '客户端未登记' })
  return Number(id)
}

async function userOf(conn: PoolConnection, userId: number): Promise<SessionUser> {
  const [rows] = await conn.query<RowDataPacket[]>(
    `SELECT u.id, u.sys_user_code AS code, u.name, r.sys_role_code AS role
     FROM t_sys_user u JOIN t_sys_role r ON r.id = u.role_id WHERE u.id = ? LIMIT 1`,
    [userId],
  )
  const row = rows[0]
  if (!row) throw createError({ statusCode: 400, statusMessage: '授权码无效' })
  return { id: Number(row.id), code: String(row.code), name: String(row.name), role: String(row.role) }
}

function fixedEqual(left: string, right: string) {
  const a = Buffer.from(left)
  const b = Buffer.from(right)
  if (a.length !== b.length) return false
  return timingSafeEqual(a, b)
}

function normalizeDate(value: string) {
  return value.includes('T') ? value : value.replace(' ', 'T') + 'Z'
}
