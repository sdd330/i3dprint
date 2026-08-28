<script setup>
// 负责人工作台：审核队列 + 打印机 + 活动生命周期 + 账单
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import StatusTag from '@/components/StatusTag.vue'

const router = useRouter()
const queues = ref(null)
const campaign = ref(null)
const loading = ref(true)

const STATUS_FLOW = ['待开放', '开放中', '收尾中', '已归档']

async function load() {
  loading.value = true
  try {
    const [q, meta] = await Promise.all([api.get('/admin/queues'), api.get('/meta/bootstrap')])
    queues.value = q
    campaign.value = meta.campaign
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

async function val1Appeal(o, decision) {
  await ElMessageBox.confirm(`确认${decision === 'approve' ? '同意' : decision === 'modify' ? '要求修改' : '驳回'}需求 O${o.id} 的申诉？`, 'Val1 申诉审核（§5.3）')
  await api.post(`/admin/val1-appeal/${o.id}`, { decision })
  ElMessage.success('已处理')
  load()
}

async function val2Pass(o) {
  await ElMessageBox.confirm(`确认 Val2 审核通过并生成打印任务？\n（含人工切片审核 + 内容合规审核，§7.3/§7.4）`, `需求 O${o.id}`)
  await api.post(`/admin/val2/${o.id}`, { decision: 'pass', note: '切片与配置一致，内容合规' })
  ElMessage.success('已放行，任务加入打印队列')
  load()
}

async function val2Reject(o) {
  const { value } = await ElMessageBox.prompt('驳回原因 / 问题类型说明', `驳回需求 O${o.id}（§7.6）`, {
    confirmButtonText: '参数问题（重切）', cancelButtonText: '内容不合规（终止）', distinguishCancelAndClose: true,
  }).catch(r => ({ value: null, cancelled: r === 'cancel' }))
  if (value !== null) {
    await api.post(`/admin/val2/${o.id}`, { decision: 'reject', issue_type: 'PARAMETER', note: value })
    ElMessage.success('已驳回：参数问题，重新切片')
  }
}

async function val2Content(o) {
  await ElMessageBox.confirm(`确认内容不合规并终止需求 O${o.id}？终止后不可恢复。`, '内容合规审核（§7.4）', { type: 'warning' })
  await api.post(`/admin/val2/${o.id}`, { decision: 'reject', issue_type: 'CONTENT', note: '内容不合规，需求终止' })
  ElMessage.success('已终止')
  load()
}

async function val3Pass(o) {
  await ElMessageBox.confirm(`确认 Val3 验收通过？将通过需求 O${o.id} 进入成本核算（§11）。`, 'Val3 实物验收（§9）')
  await api.post(`/admin/val3/${o.id}`, { decision: 'pass', note: '验收通过' })
  ElMessage.success('已通过，进入成本核算')
  load()
}

async function val3Fail(o) {
  const { value } = await ElMessageBox.prompt('选择问题责任类型并说明（§10）', `Val3 不通过 · 需求 O${o.id}`, {
    confirmButtonText: '设备问题', cancelButtonText: '参数问题', distinguishCancelAndClose: true,
    inputType: 'textarea',
  }).catch(() => ({ value: null }))
  if (value === null) return
  const issue_type = value === 'cancel' ? 'PARAMETER' : 'MACHINE'
  await api.post(`/admin/val3/${o.id}`, { decision: 'fail', issue_type, note: '实物验收不通过' })
  ElMessage.success(issue_type === 'MACHINE' ? '设备问题：半价重打（§10.2）' : '参数问题：调参重切重打（§10.1）')
  load()
}

async function printStart(o, job) {
  await api.post(`/admin/print/${job.id}/start`, {})
  ElMessage.success(`开始打印：${job.printer_id || 'X1C'} · 需求 O${o.id}`)
  load()
}
async function printDone(o, job) {
  await api.post(`/admin/print/${job.id}/complete`, {})
  ElMessage.success(`打印完成，进入 Val3 验收`)
  load()
}
async function printFail(job) {
  await ElMessageBox.confirm('确认打印异常并重新排队？（§16.4 不沿用原排位）', '打印异常')
  await api.post(`/admin/print/${job.id}/fail`, { note: '负责人标记异常' })
  ElMessage.success('已重新排队')
  load()
}
async function filamentCheck(o, approved) {
  await api.post(`/admin/orders/${o.id}/filament`, { approved, note: approved ? '规格/状态合格' : '不合格' })
  ElMessage.success(approved ? '耗材合格，任务已入队' : '已标记不合格')
  load()
}

const bill = ref(null)
const billVisible = ref(false)
async function showBill() {
  bill.value = (await api.get('/admin/campaign/bill')).bill
  billVisible.value = true
}

onMounted(load)
</script>

<template>
  <div class="page">
    <h1 class="page-title">负责人工作台</h1>
    <p class="page-sub">审核队列 · 打印管理 · 活动生命周期 · 账单 —— 所有操作写入审计日志（§13.4）</p>

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
          <el-button v-if="campaign?.status === '收尾中'" type="danger" @click="transitionCampaign('已归档')">归档（生成账单）</el-button>
          <el-button v-if="campaign?.status === '已归档'" @click="showBill">查看活动账单</el-button>
        </div>
      </div>
    </div>

    <!-- 审核队列 -->
    <div v-loading="loading" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px">
      <!-- Val1 申诉 -->
      <div class="card">
        <h3 style="margin: 0 0 10px">Val1 申诉审核 <el-tag size="small" round>{{ queues?.val1_appeal?.length || 0 }}</el-tag></h3>
        <div v-for="o in queues?.val1_appeal || []" :key="o.id" class="queue-item">
          <b>O{{ o.id }} · {{ o.name }}</b>
          <div class="muted" style="font-size: 12.5px">{{ o.user }} · {{ o.appeal?.note || '接受风险' }}</div>
          <div class="muted" style="font-size: 12.5px">警告项：{{ o.val1?.items?.filter(i => i.level !== 'pass').map(i => i.name).join('、') }}</div>
          <div style="margin-top: 6px; display: flex; gap: 6px">
            <el-button size="small" type="success" @click="val1Appeal(o, 'approve')">同意进入</el-button>
            <el-button size="small" type="warning" @click="val1Appeal(o, 'modify')">要求修改</el-button>
            <el-button size="small" type="danger" @click="val1Appeal(o, 'reject')">驳回</el-button>
          </div>
        </div>
        <el-empty v-if="!queues?.val1_appeal?.length" description="无待审申诉" :image-size="50" />
      </div>

      <!-- Val2 审核 -->
      <div class="card">
        <h3 style="margin: 0 0 10px">Val2 切片审核 <el-tag size="small" round>{{ queues?.val2_pending?.length || 0 }}</el-tag></h3>
        <div v-for="o in queues?.val2_pending || []" :key="o.id" class="queue-item">
          <b>O{{ o.id }} · {{ o.name }}</b>
          <div class="muted" style="font-size: 12.5px">{{ o.user }} · 预计 {{ Math.round(o.slice?.est_time_sec / 60) }}min / {{ o.slice?.est_weight_g }}g · 自备耗材{{ o.self_filament ? '✓' : '✗' }}</div>
          <div class="mono muted" style="font-size: 11.5px">Val2 自动检查：{{ o.val2auto?.result }} · 切片器：{{ o.slice?.slicer }}</div>
          <div style="margin-top: 6px; display: flex; gap: 6px">
            <el-button size="small" type="success" @click="val2Pass(o)">通过并放行</el-button>
            <el-button size="small" type="warning" @click="val2Reject(o)">驳回（参数）</el-button>
            <el-button size="small" type="danger" @click="val2Content(o)">内容不合规</el-button>
          </div>
        </div>
        <el-empty v-if="!queues?.val2_pending?.length" description="无待审切片" :image-size="50" />
      </div>

      <!-- 打印队列 -->
      <div class="card">
        <h3 style="margin: 0 0 10px">打印队列 <el-tag size="small" round>{{ queues?.print_queue?.length || 0 }}</el-tag></h3>
        <div v-for="o in queues?.print_queue || []" :key="o.id" class="queue-item">
          <b>O{{ o.id }} · {{ o.name }}</b>
          <div class="muted" style="font-size: 12.5px">
            <span v-for="j in o.print_jobs" :key="j.id" style="margin-right: 8px">
              #{{ j.seq }} {{ { queued: '排队中', blocked: '待检验' }[j.status] || j.status }}
              <el-button v-if="j.status === 'blocked' && o.self_filament" size="small" link type="success"
                         @click="filamentCheck(o, true)">耗材合格</el-button>
            </span>
          </div>
          <div style="margin-top: 6px">
            <el-button v-for="j in o.print_jobs.filter(x => x.status === 'queued')" :key="j.id" size="small" type="primary"
                       @click="printStart(o, j)">开始打印 #{{ j.seq }}</el-button>
          </div>
        </div>
        <el-empty v-if="!queues?.print_queue?.length" description="队列空闲" :image-size="50" />
      </div>

      <!-- 打印中 / 异常重排 -->
      <div class="card">
        <h3 style="margin: 0 0 10px">打印中 <el-tag size="small" round>{{ queues?.printing?.length || 0 }}</el-tag></h3>
        <div v-for="o in queues?.printing || []" :key="o.id" class="queue-item">
          <b>O{{ o.id }} · {{ o.name }}</b>
          <div class="muted" style="font-size: 12.5px">{{ o.print_jobs?.at(-1)?.printer_id }} ·
            预计 {{ Math.round((o.print_jobs?.at(-1)?.est_time_sec || 0) / 60) }}min ·
            进度 {{ Math.round((o.print_jobs?.at(-1)?.progress || 0) * 100) }}%</div>
          <div style="margin-top: 6px; display: flex; gap: 6px">
            <el-button v-for="j in o.print_jobs.filter(x => x.status === 'printing')" :key="j.id"
                       size="small" type="success" @click="printDone(o, j)">打印完成 #{{ j.seq }}</el-button>
            <el-button v-for="j in o.print_jobs.filter(x => x.status === 'printing')" :key="'f' + j.id"
                       size="small" type="danger" @click="printFail(j)">异常重排</el-button>
          </div>
        </div>
        <div v-for="p in queues?.printers || []" :key="p.id" class="queue-item">
          <b>{{ p.name }} <el-tag size="small" :type="p.status === 'idle' ? 'info' : 'warning'">{{ p.status === 'idle' ? '空闲' : '忙' }}</el-tag></b>
        </div>
        <div v-for="o in queues?.rework || []" :key="o.id" class="queue-item">
          <b>O{{ o.id }} · {{ o.name }}</b>
          <div class="muted" style="font-size: 12.5px">{{ o.issues?.at(-1)?.type || '—' }}（§10 责任判定）</div>
          <el-button size="small" @click="router.push(`/orders/${o.id}`)">处理（重切/重打）</el-button>
        </div>
      </div>

      <!-- Val3 验收 -->
      <div class="card">
        <h3 style="margin: 0 0 10px">Val3 实物验收 <el-tag size="small" round>{{ queues?.val3_pending?.length || 0 }}</el-tag></h3>
        <div v-for="o in queues?.val3_pending || []" :key="o.id" class="queue-item">
          <b>O{{ o.id }} · {{ o.name }}</b>
          <div class="muted" style="font-size: 12.5px">{{ o.user }} · 实际耗材：{{ o.print_jobs?.at(-1)?.actual_weight_g }}g</div>
          <div style="margin-top: 6px; display: flex; gap: 6px">
            <el-button size="small" type="success" @click="val3Pass(o)">验收通过</el-button>
            <el-button size="small" type="danger" @click="val3Fail(o)">不通过（判定责任）</el-button>
          </div>
        </div>
        <el-empty v-if="!queues?.val3_pending?.length" description="无待验收实物" :image-size="50" />
      </div>
    </div>

    <!-- 账单弹窗 -->
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
        <div v-if="bill.totals.total" style="display: flex; justify-content: space-between; margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--line)">
          <b class="muted">活动合计</b>
          <b class="amount" style="font-size: 18px; color: var(--accent)">¥{{ bill.totals.total.toFixed(2) }}</b>
        </div>
        <p class="muted" style="font-size: 12.5px; margin-top: 8px">活动结束后统一收款（个人收款码/当面转账），平台仅记账与成本核算（§11.4）</p>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.queue-item { border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin-bottom: 10px; }
</style>
