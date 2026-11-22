import { readBody, createError, getRequestIP } from 'h3'
import { randomToken } from '../../utils/oauth'
import { hashPassword, verifyPassword } from '../../utils/password'
import { queryRows, withTx } from '../../utils/db'
import { asHttpError } from '../../utils/http'
import { requireUser } from '../../utils/session'
import type { RowDataPacket } from 'mysql2'

interface HashRow extends RowDataPacket {
  password_hash: string
}

export default defineEventHandler(async (event) => {
  try {
    const user = await requireUser(event)
    const body = await readBody<{ oldPassword?: string; newPassword?: string }>(event)
    const oldPassword = body?.oldPassword ?? ''
    const newPassword = body?.newPassword ?? ''
    if (newPassword.length < 8 || newPassword.length > 128) {
      throw createError({ statusCode: 400, statusMessage: '新口令长度需在 8 到 128 之间' })
    }
    const rows = await queryRows<HashRow>(`SELECT password_hash FROM t_sys_user WHERE id = ? AND valid = 1 LIMIT 1`, [
      user.id,
    ])
    const stored = rows[0]?.password_hash
    if (!stored || !(await verifyPassword(oldPassword, stored))) {
      throw createError({ statusCode: 400, statusMessage: '当前口令不正确' })
    }
    const passwordHash = await hashPassword(newPassword)
    await withTx(async (conn) => {
      await conn.query(
        `UPDATE t_sys_user SET password_hash = ?, modified_user_code = ?, modified_user_name = ? WHERE id = ?`,
        [passwordHash, user.code, user.name, user.id],
      )
      await conn.query(
        `INSERT INTO t_e3dp_audit_log
          (e3dp_audit_log_code, user_id, action, target, detail, ip, create_user_code, create_user_name)
         VALUES (?, ?, 'account.password', ?, '口令已更新', ?, ?, ?)`,
        [randomToken(12).slice(0, 32), user.id, user.code, getRequestIP(event) ?? '', user.code, user.name],
      )
    })
    return { ok: true }
  } catch (error) {
    asHttpError(error)
  }
})
