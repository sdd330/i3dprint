export interface Campaign {
  code: string
  name: string
  status: number
  openDate: string | null
  closeDate: string | null
  maxParticipants: number
  orderCount: number
  remark: string | null
}

export interface ModelItem {
  code: string
  name: string
  kind: number
  summary: string
}

export interface ModelDetail extends Omit<ModelItem, 'summary'> {
  description: string
}

export interface OrderItem {
  code: string
  name: string
  status: number
  materialNo: string
  color: string
  selfFilament: boolean
  createdAt: string
  campaignCode: string
  campaignName: string
  modelCode: string | null
  modelName: string | null
}

export interface PrintJob {
  seq: number
  status: number
  printerNo: string | null
  estWeightMg: number
  actualWeightMg: number | null
  startDate: string | null
  endDate: string | null
  note: string
}

export interface OrderDetail extends OrderItem {
  filamentNote: string
  jobs: PrintJob[]
}

export interface SessionView {
  code: string
  name: string
  role: string
  admin: boolean
}

export interface HomePayload {
  campaigns: Campaign[]
  models: ModelItem[]
  orders: OrderItem[]
  campaignCount: number
  modelCount: number
  orderCount: number
}

const campaignStatus: Record<number, string> = {
  1: '待开放',
  2: '开放中',
  3: '收尾中',
  4: '已归档',
}

const modelKind: Record<number, string> = {
  1: '预设',
  2: '上传',
  3: 'AI',
}

const orderStatus: Record<number, string> = {
  1: '草稿',
  2: '申诉',
  3: '切片',
  4: '待核验',
  5: '核验失败',
}

const jobStatus: Record<number, string> = {
  1: '排队',
  2: '打印中',
  3: '完成',
  4: '失败',
  5: '阻塞',
}

function label(map: Record<number, string>, value: number) {
  return map[value] ?? String(value)
}

export function campaignStatusLabel(status: number) {
  return label(campaignStatus, status)
}

export function modelKindLabel(kind: number) {
  return label(modelKind, kind)
}

export function orderStatusLabel(status: number) {
  return label(orderStatus, status)
}

export function jobStatusLabel(status: number) {
  return label(jobStatus, status)
}

export function formatDate(value: string | null) {
  if (!value) return '未设置'
  return value.slice(0, 16).replace('T', ' ')
}

export function formatWeight(mg: number | null) {
  if (mg == null) return '未称重'
  return `${(mg / 1000).toFixed(2)} g`
}

export function safeColor(value: string) {
  return /^#[0-9a-fA-F]{6}$/.test(value) ? value : '#d946ef'
}
