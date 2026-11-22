import type { ResultSetHeader, RowDataPacket } from 'mysql2'
import { createError, getRequestIP, type H3Event } from 'h3'
import { isStaff, randomToken, type SessionUser } from './oauth'
import { getDb, queryRows, withTx } from './db'

const materials = new Set(['pla', 'petg', 'abs', 'tpu', 'asa'])

interface IdRow extends RowDataPacket {
  id: number
}

export async function createOrder(
  event: H3Event,
  user: SessionUser,
  input: { campaignCode?: string; name?: string; materialNo?: string; color?: string; remark?: string },
) {
  const campaignCode = (input.campaignCode ?? '').trim()
  const name = (input.name ?? '').trim()
  const materialNo = (input.materialNo ?? 'pla').trim().toLowerCase()
  const color = (input.color ?? '#d946ef').trim()
  const remark = (input.remark ?? '').trim()
  if (!campaignCode || !name || name.length > 300) {
    throw createError({ statusCode: 400, statusMessage: '请填写活动与需求名称' })
  }
  if (!materials.has(materialNo) || !/^#[0-9a-fA-F]{6}$/.test(color) || remark.length > 300) {
    throw createError({ statusCode: 400, statusMessage: '材料、颜色或备注不正确' })
  }
  const campaigns = await queryRows<IdRow>(
    `SELECT id FROM t_e3dp_campaign WHERE valid = 1 AND status = 2 AND e3dp_campaign_code = ? LIMIT 1`,
    [campaignCode],
  )
  const campaignId = campaigns[0]?.id
  if (!campaignId) throw createError({ statusCode: 400, statusMessage: '活动未开放' })
  const code = randomToken(12).slice(0, 32)
  await withTx(async (conn) => {
    await conn.query(
      `INSERT INTO t_e3dp_order
        (e3dp_order_code, campaign_id, user_id, name, status, material_no, color,
         filament_note, cost, reprint_rate, timeline, remark, create_user_code, create_user_name)
       VALUES (?, ?, ?, ?, 1, ?, ?, '', JSON_OBJECT(), JSON_OBJECT(), JSON_ARRAY(), ?, ?, ?)`,
      [code, campaignId, user.id, name, materialNo, color, remark || null, user.code, user.name],
    )
    await conn.query(
      `INSERT INTO t_e3dp_audit_log
        (e3dp_audit_log_code, user_id, action, target, detail, ip, create_user_code, create_user_name)
       VALUES (?, ?, 'order.create', ?, ?, ?, ?, ?)`,
      [randomToken(12).slice(0, 32), user.id, code, name, getRequestIP(event) ?? '', user.code, user.name],
    )
  })
  return { code }
}

const strengths = new Set(['轻量', '标准', '坚固', '超坚固'])

export async function savePrintRequirement(
  user: SessionUser,
  code: string,
  input: { materialNo: string; color: string; strength: string; note: string },
) {
  const materialNo = input.materialNo.trim().toLowerCase()
  const color = input.color.trim()
  const strength = input.strength.trim()
  const note = input.note.trim()
  if (!materials.has(materialNo) || !/^#[0-9a-fA-F]{6}$/.test(color) || !strengths.has(strength) || note.length > 300) {
    throw createError({ statusCode: 400, statusMessage: '打印需求不正确' })
  }
  const params: unknown[] = [materialNo, color, strength, note || null, user.code, user.name, code]
  let ownerSql = ''
  if (!isStaff(user)) {
    ownerSql = ' AND user_id = ?'
    params.push(user.id)
  }
  const [result] = await getDb().query<ResultSetHeader>(
    `UPDATE t_e3dp_order
     SET material_no = ?, color = ?, params = JSON_OBJECT('strength', ?), remark = ?,
         modified_user_code = ?, modified_user_name = ?
     WHERE valid = 1 AND e3dp_order_code = ?${ownerSql}`,
    params,
  )
  if (result.affectedRows !== 1) throw createError({ statusCode: 404, statusMessage: '不存在' })
  return { code }
}
