<script setup>
// 负责人工作台：Val1 人工复核（标记项）· 打印清单 · 打印执行 · Val3 验收 · 活动生命周期
// 2026-10：Val2 切片审核暂缓（人工复核对象改为 Val1 标记的潜在问题）；收费信息暂时隐去
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { useAppStore } from '@/stores'

const router = useRouter()
const app = useAppStore()
const queues = ref(null)
const campaign = ref(null)
const loading = ref(true)

const STATUS_FLOW = ['待开放', '开放中', '收尾中', '已归档']
const billingVisible = computed(() => app.billingVisible)

async function load() {
  loading.value = true
  try {
    const [q, meta] = await Promise.all([api.get('/admin/queues'), api.get('/meta/bootstrap')])
    queues.value = q
    campaign.value = meta.campaign
    app.meta = meta
  } finally {
    loading.value = false
  }
}

async function transitionCampaign(to) {
  await ElMessageBox.confirm(`确认将活动从「${campaign.value.status}」切换到「${to}」？`, '活动生命周期（§12.1）')
  await api.post('/admin/campaign/transition', { to })
  ElMessage.success(`活动状态 → ${to}`)
  load()
}

// —— Val1 人工复核（替代原申诉审核）——
async function val1Review(o, decision) {
  const label = { approve: '放行（进入打印需求配置）', modify: '要求修改模型', reject: '终止需求' }[decision]
  const { value } = await ElMessageBox.prompt(
    `需求 O${o.id}「${o.name}」标记项：${(o.val1?.flagged_items || []).map(i => i.name).join('、') || '无'}`
    + `\n\n确认「${label}」？可补充说明：`,
    'Val1 人工复核', { inputPlaceholder: '复核说明（可选）', inputValue: '', confirmButtonText: '确认' }
  ).catch(() => ({}))
  if (value === undefined) return
  await api.post(`/admin/val1-review/${o.id}`, { decision, note: value })
  ElMessage.success('已处理')
  load()
}

// —— 打印清单 ——
const manifestDialog = ref(false)
const manifestRow = ref(null)
function openManifest(row) {
  manifestRow.value = row
  manifestDialog.value = true
}
async function downloadModel(row) {
  try {
    const res = await fetch(`/api/models/${row.model_version_id}/file`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
    })
    if (!res.ok) throw new Error('下载失败')
    const blob = await res.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `O${row.id}-${row.name}.stl`
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function printStart(row) {
  const job = row.print_jobs.find(j => j.status === 'queued')
  if (!job) return ElMessage.warning('没有可开始的打印任务')
  await api.post(`/admin/print/${job.id}/start`, {})
  ElMessage.success(`开始打印：需求 O${row.id}`)
  load()
}
async function printDone(row, job) {
  await api.post(`/admin/print/${job.id}/complete`, {})
  ElMessage.success('打印完成，进入 Val3 验收')
  load()
}
async function printFail(job) {
  await ElMessageBox.confirm('确认打印异常并重新排队？（§16.4 不沿用原排位）', '打印异常')
  await api.post(`/admin/print/${job.id}/fail`, { note: '负责人标记异常' })
  ElMessage.success('已重新排队')
  load()
}
async function filamentCheck(row, approved) {
  await api.post(`/admin/orders/${row.id}/filament`, { approved, note: approved ? '规格/状态合格' : '不合格' })
  ElMessage.success(approved ? '耗材合格，任务已入清单' : '已标记不合格')
  load()
}

async function val3Pass(o) {
  await ElMessageBox.confirm(`确认 Val3 验收通过？需求 O${o.id} 进入结算（§9）。`, 'Val3 实物验收')
  await api.post(`/admin/val3/${o.id}`, { decision: 'pass', note: '验收通过' })
  ElMessage.success('已通过')
  load()
}

// Val3 不通过：责任判定 dialog（§9.3 / §10）
const val3Dialog = ref({ visible: false, order: null, issueType: 'PARAMETER', note: '' })
const VAL3_TYPES = [
  ['PARAMETER', '参数问题', '用户调整打印需求（材料/强度/参数）→ 重新进清单（§10.1）'],
  ['MACHINE', '设备问题', '设备处理 → 半价重打（§10.2）'],
  ['MODEL', '模型问题', '修改模型新版本 → 重走 Val1（§10.3）'],
  ['MACHINE_LIMIT', '设备能力上限', '不再重打，需求终止（§10.4）'],
]
function val3Fail(o) {
  val3Dialog.value = { visible: true, order: o, issueType: 'PARAMETER', note: '' }
}
async function val3SubmitFail() {
  const d = val3Dialog.value
  await api.post(`/admin/val3/${d.order.id}`, {
    decision: 'fail', issue_type: d.issueType, note: d.note || '实物验收不通过',
  })
  ElMessage.success(`已判定：${VAL3_TYPES.find(t => t[0] === d.issueType)?.[1]}`)
  d.visible = false
  load()
}

// 设备问题：直接入队重打（§10.2）
async function requeueReprint(o) {
  await ElMessageBox.confirm(`确认设备已处理，安排需求 O${o.id} 半价重打？`, '设备问题重打（§10.2）')
  await api.post(`/admin/orders/${o.id}/requeue`, { note: '设备已处理，半价重打入清单' })
  ElMessage.success('已重新进入打印清单（半价计费）')
  load()
}

const bill = ref(null)
const billVisible = ref(false)
async function showBill() {
  bill.value = (await api.get('/admin/campaign/bill')).bill
  billVisible.value = true
}

const MANIFEST_STATUS = { queued: '待打印', blocked: '待检验耗材', printing: '打印中' }

onMounted(load)
</script>

<template>
  <div class="page">
    <h1 class="page-title">负责人工作台</h1>
    <p class="page-sub">
      Val1 标记项复核 · 打印清单 · 打印执行 · Val3 验收 —— 所有操作写入审计日志（§13.4）
    </p>

    <!-- 活动生命周期 -->
    <div class="card" style="margin-bottom: 20px">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px">
        <div>
          <b style="font-size: 15px">{{ campaign?.name }}</b>
          <el-steps :active="STATUS_FLOW.indexOf(campaign?.status)" align-center style="max-width: 480px; margin-top: 10px">
            <el-step v-for="s in STATUS_FLOW" :key="s" :title="s" />
          </el-steps>
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px; min-width: 160px">
          <el-button v-if="campaign?.status === '待开放'" type="success" @click="transitionCampaign('开放中')">开放活动（开始接单）</el-button>
          <el-button v-if="campaign?.status === '开放中'" type="warning" @click="transitionCampaign('收尾中')">收尾（停止接单）</el-button>
          <el-button v-if="campaign?.status === '收尾中'" type="danger" @click="transitionCampaign('已归档')">归档</el-button>
          <el-button v-if="campaign?.status === '已归档' && billingVisible" @click="showBill">查看活动账单</el-button>
        </div>
      </div>
    </div>

    <div v-loading="loading" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px">
      <!-- Val1 人工复核（标记项） -->
      <div class="card">
        <h3 style="margin: 0 0 10px">
          Val1 标记项复核 <el-tag size="small" round>{{ queues?.val1_review?.length || 0 }}</el-tag>
        </h3>
        <div v-for="o in queues?.val1_review || []" :key="o.id" class="queue-item">
          <b>O{{ o.id }} · {{ o.name }}</b>
          <div class="muted" style="font-size: 12.5px">
            {{ o.user }} · Val1 {{ o.val1?.result }} · 尺寸 {{ (o.geometry?.bbox || []).join(' × ') }} mm
          </div>
          <div style="margin-top: 4px">
            <el-tag v-for="f in o.val1?.flagged_items || []" :key="f.id" size="small"
                    :type="f.level === 'fail' ? 'danger' : 'warning'" effect="plain" style="margin: 0 4px 4px 0">
              {{ f.name }}
            </el-tag>
          </div>
          <div style="margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap">
            <el-button size="small" type="success" @click="val1Review(o, 'approve')">放行</el-button>
            <el-button size="small" type="warning" @click="val1Review(o, 'modify')">要求修改</el-button>
            <el-button size="small" type="danger" @click="val1Review(o, 'reject')">终止</el-button>
          </div>
        </div>
        <el-empty v-if="!queues?.val1_review?.length" description="暂无标记项待复核" :image-size="50" />
      </div>

      <!-- 打印清单（待执行打印） -->
      <div class="card" style="grid-column: span 2">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px">
          <h3 style="margin: 0">
            打印清单 <el-tag size="small" round>{{ queues?.print_queue?.length || 0 }}</el-tag>
          </h3>
          <el-button size="small" @click="router.push('/admin/manifest')">整页清单 / 打印 →</el-button>
        </div>
        <el-table :data="queues?.print_queue || []" size="small">
          <el-table-column label="需求" width="180">
            <template #default="{ row }">
              <b>O{{ row.id }}</b> · {{ row.name }}
              <div class="muted mono" style="font-size: 11px">{{ row.user }}</div>
            </template>
          </el-table-column>
          <el-table-column label="材料 / 颜色" width="150">
            <template #default="{ row }">
              <span>{{ app.materials.find(m => m.id === row.material_id)?.name || row.material_id }}</span>
              <span :style="{ display: 'inline-block', width: 10, height: 10, borderRadius: 3, background: row.color, marginLeft: 6, border: '1px solid var(--line)' }" />
              <div v-if="row.self_filament" class="muted" style="font-size: 11.5px">
                自备耗材{{ row.filament_approved ? '（已检）' : '（待检）' }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="强度 / 参数" width="170">
            <template #default="{ row }">
              <div>{{ row.params?.strength_name || '—' }}</div>
              <div class="mono muted" style="font-size: 11px">
                {{ row.params?.layer_height }}mm · 壁厚{{ row.params?.wall_loops }}圈 · 填充{{ row.params?.infill_density }}%
              </div>
            </template>
          </el-table-column>
          <el-table-column label="尺寸" width="130">
            <template #default="{ row }">
              <span class="mono" style="font-size: 11.5px">{{ (row.geometry?.bbox || []).join(' × ') }} mm</span>
            </template>
          </el-table-column>
          <el-table-column label="预估" width="100">
            <template #default="{ row }">
              <span class="mono" style="font-size: 11.5px">
                {{ row.print_jobs?.at(-1)?.est_weight_g }}g<br />{{ Math.round((row.print_jobs?.at(-1)?.est_time_sec || 0) / 60) }}min
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="230">
            <template #default="{ row }">
              <el-button size="small" @click="openManifest(row)">清单</el-button>
              <el-button size="small" @click="downloadModel(row)">模型</el-button>
              <el-button v-if="row.self_filament && !row.filament_approved" size="small" type="warning"
                         @click="filamentCheck(row, true)">耗材合格</el-button>
              <el-button size="small" type="primary" :disabled="row.self_filament && !row.filament_approved"
                         @click="printStart(row)">开始打印</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!queues?.print_queue?.length" description="清单为空" :image-size="50" />
      </div>

      <!-- 打印中 / 打印机 / 返工 -->
      <div class="card">
        <h3 style="margin: 0 0 10px">打印中 <el-tag size="small" round>{{ queues?.printing?.length || 0 }}</el-tag></h3>
        <div v-for="o in queues?.printing || []" :key="o.id" class="queue-item">
          <b>O{{ o.id }} · {{ o.name }}</b>
          <div class="muted" style="font-size: 12.5px">
            {{ o.print_jobs?.at(-1)?.printer_id }} · 进度 {{ Math.round((o.print_jobs?.at(-1)?.progress || 0) * 100) }}%
            · 预估 {{ Math.round((o.print_jobs?.at(-1)?.est_time_sec || 0) / 60) }}min
          </div>
          <div style="margin-top: 6px; display: flex; gap: 6px">
            <el-button v-for="j in o.print_jobs.filter(x => x.status === 'printing')" :key="j.id"
                       size="small" type="success" @click="printDone(o, j)">打印完成 #{{ j.seq }}</el-button>
            <el-button v-for="j in o.print_jobs.filter(x => x.status === 'printing')" :key="'f' + j.id"
                       size="small" type="danger" @click="printFail(j)">异常重排</el-button>
          </div>
        </div>
        <div v-for="p in queues?.printers || []" :key="p.id" class="queue-item">
          <b>{{ p.name }}</b>
          <el-tag size="small" :type="p.status === 'idle' ? 'info' : 'warning'" style="margin-left: 6px">
            {{ p.status === 'idle' ? '空闲' : '忙' }}
          </el-tag>
        </div>
        <div v-for="o in queues?.rework || []" :key="o.id" class="queue-item">
          <b>O{{ o.id }} · {{ o.name }}</b>
          <div class="muted" style="font-size: 12.5px">
            <el-tag size="small" :type="o.issues?.at(-1)?.type === 'MACHINE' ? 'warning' : 'info'">
              {{ { PARAMETER: '参数问题', MACHINE: '设备问题', MODEL: '模型问题', MACHINE_LIMIT: '设备能力上限' }[o.issues?.at(-1)?.type] || '—' }}
            </el-tag>
            <span style="margin-left: 6px">{{ o.issues?.at(-1)?.description }}</span>
          </div>
          <div style="margin-top: 6px; display: flex; gap: 6px">
            <el-button v-if="o.issues?.at(-1)?.type === 'MACHINE'" size="small" type="warning" @click="requeueReprint(o)">
              设备已处理，重新入清单
            </el-button>
            <el-button v-else size="small" @click="router.push(`/orders/${o.id}`)">查看（等用户处理）</el-button>
          </div>
        </div>
        <el-empty v-if="!queues?.printing?.length && !queues?.rework?.length" description="无进行中的打印" :image-size="50" />
      </div>

      <!-- Val3 验收 -->
      <div class="card">
        <h3 style="margin: 0 0 10px">Val3 实物验收 <el-tag size="small" round>{{ queues?.val3_pending?.length || 0 }}</el-tag></h3>
        <div v-for="o in queues?.val3_pending || []" :key="o.id" class="queue-item">
          <b>O{{ o.id }} · {{ o.name }}</b>
          <div class="muted" style="font-size: 12.5px">
            {{ o.user }} · {{ o.params?.strength_name || '' }} · 实际耗材 {{ o.print_jobs?.at(-1)?.actual_weight_g }}g
          </div>
          <div style="margin-top: 6px; display: flex; gap: 6px">
            <el-button size="small" type="success" @click="val3Pass(o)">验收通过</el-button>
            <el-button size="small" type="danger" @click="val3Fail(o)">不通过（判定责任）</el-button>
          </div>
        </div>
        <el-empty v-if="!queues?.val3_pending?.length" description="无待验收实物" :image-size="50" />
      </div>

      <!-- 等待用户填写打印需求 -->
      <div class="card">
        <h3 style="margin: 0 0 10px">待填打印需求 <el-tag size="small" round>{{ queues?.print_config?.length || 0 }}</el-tag></h3>
        <div v-for="o in queues?.print_config || []" :key="o.id" class="queue-item">
          <b>O{{ o.id }} · {{ o.name }}</b>
          <div class="muted" style="font-size: 12.5px">
            {{ o.user }} · Val1 {{ o.val1?.result }}，等待用户选材料 / 强度 / 参数
          </div>
        </div>
        <el-empty v-if="!queues?.print_config?.length" description="无等待中的需求" :image-size="50" />
      </div>
    </div>

    <!-- 清单详情 -->
    <el-dialog v-model="manifestDialog" width="640px">
      <template #header><b>打印清单 · 需求 O{{ manifestRow?.id }}</b></template>
      <div v-if="manifestRow" style="display: flex; flex-direction: column; gap: 10px">
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="需求">{{ manifestRow.name }}</el-descriptions-item>
          <el-descriptions-item label="用户">{{ manifestRow.user }}</el-descriptions-item>
          <el-descriptions-item label="材料">{{ app.materials.find(m => m.id === manifestRow.material_id)?.name }}</el-descriptions-item>
          <el-descriptions-item label="颜色">{{ manifestRow.color }}</el-descriptions-item>
          <el-descriptions-item label="强度">{{ manifestRow.params?.strength_name }}</el-descriptions-item>
          <el-descriptions-item label="层高">{{ manifestRow.params?.layer_height }} mm</el-descriptions-item>
          <el-descriptions-item label="壁厚圈数">{{ manifestRow.params?.wall_loops }}</el-descriptions-item>
          <el-descriptions-item label="填充">{{ manifestRow.params?.infill_density }}%（{{ manifestRow.params?.infill_pattern }}）</el-descriptions-item>
          <el-descriptions-item label="尺寸">{{ (manifestRow.geometry?.bbox || []).join(' × ') }} mm</el-descriptions-item>
          <el-descriptions-item label="体积">{{ manifestRow.val1?.stats?.volume_cm3 }} cm³</el-descriptions-item>
          <el-descriptions-item label="支撑">{{ manifestRow.params?.supports === 'auto' ? '自动（按角度）' : '无' }}</el-descriptions-item>
          <el-descriptions-item label="自备耗材">
            {{ manifestRow.self_filament ? (manifestRow.filament_approved ? '是 · 已检验合格' : '是 · 待检验') : '平台耗材' }}
          </el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="manifestRow.params?.operator_note" type="info" :closable="false"
                  :title="`用户备注：${manifestRow.params.operator_note}`" />
        <div class="muted" style="font-size: 12.5px">
          预估 {{ manifestRow.print_jobs?.at(-1)?.est_weight_g }}g /
          {{ Math.round((manifestRow.print_jobs?.at(-1)?.est_time_sec || 0) / 60) }}min（几何估算，实际以切片结果为准）
        </div>
        <div style="display: flex; gap: 8px">
          <el-button @click="downloadModel(manifestRow)">下载模型</el-button>
          <el-button type="primary" @click="printStart(manifestRow)">开始打印</el-button>
        </div>
      </div>
    </el-dialog>

    <!-- Val3 责任判定 -->
    <el-dialog v-model="val3Dialog.visible" :title="`Val3 不通过 · 需求 O${val3Dialog.order?.id}`" width="520px">
      <el-alert type="error" :closable="false" show-icon style="margin-bottom: 12px"
                title="实物验收不通过，请判定问题责任（§9.3）" />
      <el-form label-position="top">
        <el-form-item label="问题类型（§10 处理路径不同）">
          <el-radio-group v-model="val3Dialog.issueType" style="display: flex; flex-direction: column; gap: 6px">
            <el-radio v-for="[v, name, desc] in VAL3_TYPES" :key="v" :value="v">
              {{ name }}<span class="muted" style="font-size: 12px"> — {{ desc }}</span>
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="问题描述">
          <el-input v-model="val3Dialog.note" type="textarea" :rows="2" placeholder="如：表面拉丝严重 / 喷嘴堵塞导致层间分离…" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="val3Dialog.visible = false">取消</el-button>
        <el-button type="danger" @click="val3SubmitFail">确认判定</el-button>
      </template>
    </el-dialog>

    <!-- 账单（收费信息暂时隐去） -->
    <el-dialog v-model="billVisible" title="活动账单（§12.4）" width="640px">
      <template v-if="bill">
        <el-table :data="bill.rows" size="small">
          <el-table-column prop="order_id" label="需求" width="70">
            <template #default="{ row }">O{{ row.order_id }}</template>
          </el-table-column>
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="user" label="用户" width="90" />
          <el-table-column prop="filament" label="耗材" width="80" />
          <el-table-column prop="maintenance" label="维护" width="80" />
          <el-table-column prop="total" label="合计" width="90">
            <template #default="{ row }"><span class="amount">¥{{ row.total.toFixed(2) }}</span></template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!bill.rows.length" description="暂无已结需求" :image-size="60" />
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.queue-item { border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin-bottom: 10px; }
</style>
