import type { RowDataPacket } from 'mysql2'
import { createError, type H3Event } from 'h3'
import { writeAudit } from './audit'
import { queryRows, withTx } from './db'
import type { SessionUser } from './oauth'
import { hashPassword, verifyPassword } from './password'

interface HashRow extends RowDataPacket {
  password_hash: string
}

export async function changePassword(event: H3Event, user: SessionUser, oldPassword: string, newPassword: string) {
  if (newPassword.length < 8 || newPassword.length > 128) {
    throw createError({ statusCode: 400, message: '新口令长度需在 8 到 128 之间' })
  }
  const rows = await queryRows<HashRow>(`SELECT password_hash FROM t_sys_user WHERE id = ? AND valid = 1 LIMIT 1`, [
    user.id,
  ])
  const stored = rows[0]?.password_hash
  if (!stored || !(await verifyPassword(oldPassword, stored))) {
    throw createError({ statusCode: 400, message: '当前口令不正确' })
  }
  const passwordHash = await hashPassword(newPassword)
  await withTx(async (conn) => {
    await conn.query(
      `UPDATE t_sys_user
       SET password_hash = ?, modified_user_code = ?, modified_user_name = ?, version = version + 1
       WHERE id = ?`,
      [passwordHash, user.code, user.name, user.id],
    )
    await writeAudit(conn, event, user, { action: 'account.password', target: user.code, detail: '口令已更新' })
  })
}
