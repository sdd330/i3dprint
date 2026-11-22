import { randomBytes, scrypt } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { promisify } from 'node:util'
import mysql from 'mysql2/promise'

const password = process.env.SEED_PASSWORD
if (!password) {
  console.error('缺少 SEED_PASSWORD')
  process.exit(1)
}

const scryptAsync = promisify(scrypt)
const N = 131072
const r = 8
const p = 1
const salt = randomBytes(16)
const key = await scryptAsync(password, salt, 32, { N, r, p, maxmem: 256 * 1024 * 1024 })
const passwordHash = `scrypt$${N}$${r}$${p}$${salt.toString('base64url')}$${key.toString('base64url')}`

const env = {}
for (const line of readFileSync(join(homedir(), '.mysql_env'), 'utf8').split('\n')) {
  const trimmed = line.trim()
  if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue
  const raw = trimmed.startsWith('export ') ? trimmed.slice(7) : trimmed
  const eq = raw.indexOf('=')
  env[raw.slice(0, eq).trim()] = raw.slice(eq + 1).trim().replace(/^['"]|['"]$/g, '')
}

const db = await mysql.createConnection({
  host: env.MYSQL_HOST,
  port: Number(env.MYSQL_PORT || 3306),
  user: env.MYSQL_USER || env.MYSQL_ROOT,
  password: env.MYSQL_PASSWORD,
  database: 'i3dprint',
  charset: 'utf8mb4',
})

await db.query(
  `INSERT INTO t_sys_role (sys_role_code, name, permissions, builtin, create_user_code, create_user_name)
   VALUES ('root', '超级管理员', JSON_ARRAY('*'), 1, 'root', 'root')
   ON DUPLICATE KEY UPDATE name = VALUES(name), builtin = 1, valid = 1`,
)
await db.query(
  `INSERT INTO t_sys_user
     (sys_user_code, name, grade, password_hash, role_id, is_active, create_user_code, create_user_name)
   VALUES ('root', 'root', '', ?, (SELECT id FROM t_sys_role WHERE sys_role_code = 'root'), 1, 'root', 'root')
   ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash), is_active = 1, valid = 1`,
  [passwordHash],
)
await db.query(
  `INSERT INTO t_sys_oauth_client (sys_oauth_client_code, name, redirect_path, create_user_code, create_user_name)
   VALUES ('violet-z', 'Violet Z', '/oauth/callback', 'root', 'root')
   ON DUPLICATE KEY UPDATE redirect_path = VALUES(redirect_path), valid = 1`,
)
await db.end()
console.log('root 账号已写入')
