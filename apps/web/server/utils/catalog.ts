import type { RowDataPacket } from 'mysql2'
import { createError } from 'h3'
import type { Campaign, HomePayload, ModelDetail, ModelItem, OrderDetail, OrderItem, PrintJob } from '#shared/print'
import { queryRows } from './db'

interface CountRow extends RowDataPacket {
  total: number | string
}

interface CampaignRow extends RowDataPacket {
  code: string
  name: string
  status: number
  openDate: string | null
  closeDate: string | null
  maxParticipants: number
  orderCount: number | string
  remark: string | null
}

interface ModelRow extends RowDataPacket {
  code: string
  name: string
  kind: number
  summary: string
  description?: string
}

interface OrderRow extends RowDataPacket {
  code: string
  name: string
  status: number
  materialNo: string
  color: string
  selfFilament: number
  userId: number
  createdAt: string
  campaignCode: string
  campaignName: string
  modelCode: string | null
  modelName: string | null
  filamentNote?: string
}

interface JobRow extends RowDataPacket {
  seq: number
  status: number
  printerNo: string | null
  estWeightMg: number
  actualWeightMg: number | null
  startDate: string | null
  endDate: string | null
  note: string
}

const campaignSql = `
  SELECT c.e3dp_campaign_code AS code, c.name, c.status,
         c.open_date AS openDate, c.close_date AS closeDate,
         c.max_participants AS maxParticipants, c.remark,
         (SELECT COUNT(*) FROM t_e3dp_order o WHERE o.campaign_id = c.id AND o.valid = 1) AS orderCount
  FROM t_e3dp_campaign c
  WHERE c.valid = 1
`

const modelSql = `
  SELECT e3dp_model_code AS code, name, kind,
         SUBSTRING(description, 1, 160) AS summary
  FROM t_e3dp_model
  WHERE valid = 1
`

const orderSql = `
  SELECT o.e3dp_order_code AS code, o.name, o.status,
         o.material_no AS materialNo, o.color, o.self_filament AS selfFilament,
         o.user_id AS userId, o.create_date AS createdAt,
         c.e3dp_campaign_code AS campaignCode, c.name AS campaignName,
         m.e3dp_model_code AS modelCode, m.name AS modelName
  FROM t_e3dp_order o
  JOIN t_e3dp_campaign c ON c.id = o.campaign_id
  LEFT JOIN t_e3dp_model m ON m.id = o.model_id
  WHERE o.valid = 1
`

function mapCampaign(row: CampaignRow): Campaign {
  return {
    code: row.code,
    name: row.name,
    status: Number(row.status),
    openDate: row.openDate,
    closeDate: row.closeDate,
    maxParticipants: Number(row.maxParticipants),
    orderCount: Number(row.orderCount),
    remark: row.remark,
  }
}

function mapModel(row: ModelRow): ModelItem {
  return {
    code: row.code,
    name: row.name,
    kind: Number(row.kind),
    summary: row.summary ?? '',
  }
}

function mapOrder(row: OrderRow): OrderItem {
  return {
    code: row.code,
    name: row.name,
    status: Number(row.status),
    materialNo: row.materialNo,
    color: row.color,
    selfFilament: row.selfFilament === 1,
    createdAt: row.createdAt,
    campaignCode: row.campaignCode,
    campaignName: row.campaignName,
    modelCode: row.modelCode,
    modelName: row.modelName,
  }
}

async function countOf(table: string) {
  const rows = await queryRows<CountRow>(`SELECT COUNT(*) AS total FROM ${table} WHERE valid = 1`)
  return Number(rows[0]?.total ?? 0)
}

export async function listCampaigns() {
  const rows = await queryRows<CampaignRow>(`${campaignSql} ORDER BY c.id DESC LIMIT 100`)
  return rows.map(mapCampaign)
}

export async function listModels() {
  const rows = await queryRows<ModelRow>(`${modelSql} ORDER BY id DESC LIMIT 100`)
  return rows.map(mapModel)
}

export async function getModel(code: string) {
  const rows = await queryRows<ModelRow>(
    `SELECT e3dp_model_code AS code, name, kind, description AS summary, description
     FROM t_e3dp_model WHERE valid = 1 AND e3dp_model_code = ? LIMIT 1`,
    [code],
  )
  const row = rows[0]
  if (!row) throw createError({ statusCode: 404, statusMessage: '不存在' })
  const detail: ModelDetail = {
    code: row.code,
    name: row.name,
    kind: Number(row.kind),
    description: row.description ?? '',
  }
  return detail
}

export async function listOrders(ownerId?: number) {
  const rows = await queryRows<OrderRow>(
    ownerId == null
      ? `${orderSql} ORDER BY o.id DESC LIMIT 100`
      : `${orderSql} AND o.user_id = ? ORDER BY o.id DESC LIMIT 100`,
    ownerId == null ? [] : [ownerId],
  )
  return rows.map(mapOrder)
}

export async function getOrder(code: string, ownerId?: number): Promise<OrderDetail> {
  const rows = await queryRows<OrderRow>(
    `${orderSql.replace('WHERE o.valid = 1', 'WHERE o.valid = 1 AND o.e3dp_order_code = ?')}
     LIMIT 1`.replace(
      'o.create_date AS createdAt,',
      'o.create_date AS createdAt, o.filament_note AS filamentNote,',
    ),
    [code],
  )
  const row = rows[0]
  if (!row || (ownerId != null && Number(row.userId) !== ownerId)) {
    throw createError({ statusCode: 404, statusMessage: '不存在' })
  }
  const jobs = await queryRows<JobRow>(
    `SELECT j.print_seq AS seq, j.status, j.printer_no AS printerNo,
            j.est_weight AS estWeightMg, j.actual_weight AS actualWeightMg,
            j.start_date AS startDate, j.end_date AS endDate, j.note
     FROM t_e3dp_print_job j
     JOIN t_e3dp_order o ON o.id = j.order_id
     WHERE j.valid = 1 AND o.e3dp_order_code = ?
     ORDER BY j.print_seq`,
    [code],
  )
  return {
    ...mapOrder(row),
    filamentNote: row.filamentNote ?? '',
    jobs: jobs.map(mapJob),
  }
}

function mapJob(row: JobRow): PrintJob {
  return {
    seq: Number(row.seq),
    status: Number(row.status),
    printerNo: row.printerNo,
    estWeightMg: Number(row.estWeightMg),
    actualWeightMg: row.actualWeightMg == null ? null : Number(row.actualWeightMg),
    startDate: row.startDate,
    endDate: row.endDate,
    note: row.note ?? '',
  }
}

export async function loadHome(ownerId?: number): Promise<HomePayload> {
  const orderQuery =
    ownerId == null
      ? queryRows<OrderRow>(`${orderSql} ORDER BY o.id DESC LIMIT 6`)
      : queryRows<OrderRow>(`${orderSql} AND o.user_id = ? ORDER BY o.id DESC LIMIT 6`, [ownerId])
  const orderCountQuery =
    ownerId == null
      ? countOf('t_e3dp_order')
      : queryRows<CountRow>(`SELECT COUNT(*) AS total FROM t_e3dp_order WHERE valid = 1 AND user_id = ?`, [ownerId]).then(
          (rows) => Number(rows[0]?.total ?? 0),
        )
  const [campaigns, models, orders, campaignCount, modelCount, orderCount] = await Promise.all([
    queryRows<CampaignRow>(`${campaignSql} ORDER BY c.id DESC LIMIT 3`).then((rows) => rows.map(mapCampaign)),
    queryRows<ModelRow>(`${modelSql} ORDER BY id DESC LIMIT 4`).then((rows) => rows.map(mapModel)),
    orderQuery.then((rows) => rows.map(mapOrder)),
    countOf('t_e3dp_campaign'),
    countOf('t_e3dp_model'),
    orderCountQuery,
  ])
  return { campaigns, models, orders, campaignCount, modelCount, orderCount }
}
