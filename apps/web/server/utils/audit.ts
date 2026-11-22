import type { H3Event } from 'h3'
import type { PoolConnection } from 'mysql2/promise'
import { clientIp } from './http'
import { newCode, type SessionUser } from './oauth'

export async function writeAudit(
  conn: PoolConnection,
  event: H3Event,
  user: SessionUser,
  entry: { action: string; target: string; detail: string },
) {
  await conn.query(
    `INSERT INTO t_e3dp_audit_log
      (e3dp_audit_log_code, user_id, action, target, detail, ip, create_user_code, create_user_name)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    [newCode(), user.id, entry.action, entry.target, entry.detail, clientIp(event), user.code, user.name],
  )
}
