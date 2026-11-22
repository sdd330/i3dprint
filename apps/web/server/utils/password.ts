import { scrypt, timingSafeEqual } from 'node:crypto'
import { promisify } from 'node:util'

const scryptAsync = promisify(scrypt)

const N = 131072
const R = 8
const P = 1

export async function hashPassword(password: string) {
  const { randomBytes } = await import('node:crypto')
  const salt = randomBytes(16)
  const key = (await scryptAsync(password, salt, 32, {
    N,
    r: R,
    p: P,
    maxmem: 256 * 1024 * 1024,
  })) as Buffer
  return `scrypt$${N}$${R}$${P}$${salt.toString('base64url')}$${key.toString('base64url')}`
}

export async function verifyPassword(password: string, stored: string) {
  const parts = stored.split('$')
  if (parts.length !== 6 || parts[0] !== 'scrypt') return false
  const n = Number(parts[1])
  const r = Number(parts[2])
  const p = Number(parts[3])
  if (!Number.isFinite(n) || !Number.isFinite(r) || !Number.isFinite(p)) return false
  const salt = Buffer.from(parts[4] ?? '', 'base64url')
  const expected = Buffer.from(parts[5] ?? '', 'base64url')
  const actual = (await scryptAsync(password, salt, expected.length, {
    N: n,
    r,
    p,
    maxmem: 256 * 1024 * 1024,
  })) as Buffer
  if (actual.length !== expected.length) return false
  return timingSafeEqual(actual, expected)
}
