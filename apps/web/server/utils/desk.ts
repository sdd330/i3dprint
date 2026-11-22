import type { RowDataPacket } from 'mysql2'
import { createError } from 'h3'
import { queryRows } from './db'

export interface DeskPayload {
  columns: string[]
  rows: string[][]
}

function text(value: unknown) {
  if (value == null) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

async function table(sql: string, columns: string[]) {
  const records = await queryRows<RowDataPacket>(sql)
  return {
    columns,
    rows: records.map((row) => columns.map((column) => text(row[column]))),
  }
}

const views: Record<string, () => Promise<DeskPayload>> = {
  summary: async () => {
    const counts = await queryRows<RowDataPacket>(
      `SELECT '活动' AS label, COUNT(*) AS total FROM t_e3dp_campaign WHERE valid = 1
       UNION ALL SELECT '模型', COUNT(*) FROM t_e3dp_model WHERE valid = 1
       UNION ALL SELECT '需求', COUNT(*) FROM t_e3dp_order WHERE valid = 1
       UNION ALL SELECT '打印任务', COUNT(*) FROM t_e3dp_print_job WHERE valid = 1
       UNION ALL SELECT '用户', COUNT(*) FROM t_sys_user WHERE valid = 1
       UNION ALL SELECT '问答', COUNT(*) FROM t_e3dp_qa_ticket WHERE valid = 1`,
    )
    return {
      columns: ['label', 'total'],
      rows: counts.map((row) => [text(row.label), text(row.total)]),
    }
  },
  campaigns: () =>
    table(
      `SELECT e3dp_campaign_code, name, status, max_participants, open_date, close_date
       FROM t_e3dp_campaign WHERE valid = 1 ORDER BY id DESC LIMIT 100`,
      ['e3dp_campaign_code', 'name', 'status', 'max_participants', 'open_date', 'close_date'],
    ),
  users: () =>
    table(
      `SELECT u.sys_user_code, u.name, u.grade, r.sys_role_code AS role, u.is_active, u.contact_mask
       FROM t_sys_user u JOIN t_sys_role r ON r.id = u.role_id
       WHERE u.valid = 1 ORDER BY u.id LIMIT 200`,
      ['sys_user_code', 'name', 'grade', 'role', 'is_active', 'contact_mask'],
    ),
  roles: () =>
    table(
      `SELECT sys_role_code, name, permissions, builtin FROM t_sys_role WHERE valid = 1 ORDER BY id`,
      ['sys_role_code', 'name', 'permissions', 'builtin'],
    ),
  jobs: () =>
    table(
      `SELECT j.e3dp_print_job_code, o.name AS order_name, j.print_seq, j.status, j.printer_no, j.est_weight
       FROM t_e3dp_print_job j JOIN t_e3dp_order o ON o.id = j.order_id
       WHERE j.valid = 1 ORDER BY j.id DESC LIMIT 200`,
      ['e3dp_print_job_code', 'order_name', 'print_seq', 'status', 'printer_no', 'est_weight'],
    ),
  audits: () =>
    table(
      `SELECT action, target, create_user_name, ip, create_date
       FROM t_e3dp_audit_log WHERE valid = 1 ORDER BY id DESC LIMIT 100`,
      ['action', 'target', 'create_user_name', 'ip', 'create_date'],
    ),
  settings: () =>
    table(
      `SELECT setting_key, label, category,
              CASE WHEN value_type = 5 THEN '已隐藏' ELSE setting_value END AS setting_value
       FROM t_e3dp_app_setting WHERE valid = 1 ORDER BY category, setting_key LIMIT 200`,
      ['setting_key', 'label', 'category', 'setting_value'],
    ),
  config: () =>
    table(
      `SELECT e3dp_config_template_code, name, is_default, modified_date
       FROM t_e3dp_config_template WHERE valid = 1 ORDER BY id DESC`,
      ['e3dp_config_template_code', 'name', 'is_default', 'modified_date'],
    ),
  qa: () =>
    table(
      `SELECT e3dp_qa_ticket_code, title, author_name, status, create_date
       FROM t_e3dp_qa_ticket WHERE valid = 1 ORDER BY id DESC LIMIT 100`,
      ['e3dp_qa_ticket_code', 'title', 'author_name', 'status', 'create_date'],
    ),
  kb: () =>
    table(
      `SELECT file_name, chunk_count, embedding_model FROM t_e3dp_kb_source WHERE valid = 1 ORDER BY id DESC`,
      ['file_name', 'chunk_count', 'embedding_model'],
    ),
}

export async function loadDesk(view: string) {
  const load = views[view]
  if (!load) throw createError({ statusCode: 404, statusMessage: '不存在' })
  return load()
}

export const listAudits = () => loadDesk('audits')
export const listStaffUsers = () => loadDesk('users')
export const listStaffRoles = () => loadDesk('roles')
export const listManifest = () => loadDesk('jobs')
export const listSettings = () => loadDesk('settings')
