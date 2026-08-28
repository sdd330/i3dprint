<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { useAppStore } from '@/stores'
import StatusTag from '@/components/StatusTag.vue'
import AdvancedParamsForm from '@/components/AdvancedParamsForm.vue'
import ChainView from '@/components/ChainView.vue'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const order = ref(null)
const loading = ref(true)
const feedbackText = ref('')
const resliceParams = ref({ preset: 'standard' })
const advancedParams = reactive({ layer_height: 0.2, wall_loops: 2, infill_density: 20, infill_pattern: 'grid', outer_wall_speed: 200, travel_speed: 500, nozzle_temperature: 220, bed_temperature: 65, enable_support: '0', support_type: 'normal(auto)', support_threshold_angle: 30, retraction_length: 0.8 })
const resliceAdvanced = ref(false)
const resliceDialog = ref(false)

const id = Number(route.params.id)
const material = computed(() => app.meta?.materials?.find(m => m.id === order.value?.material_id))
const issueLabels = computed(() => ({ PARAMETER: '参数问题', MACHINE: '设备问题', MODEL: '模型问题', MACHINE_LIMIT: '设备能力上限', CONTENT: '内容不合规' }))

async function load() {
  loading.value = true
  try {
    order.value = (await api.get(`/orders/${id}`)).order
  } finally {
    loading.value = false
  }
}

async function sendFeedback() {
  if (!feedbackText.value.trim()) return
  await api.post(`/orders/${id}/feedback`, { content: feedbackText.value })
  ElMessage.success('反馈已提交')
  feedbackText.value = ''
  load()
}

async function settle() {
  await ElMessageBox.confirm('确认结清该需求，计入活动账单？', '成本核算')
  await api.post(`/orders/${id}/settle`, {})
  ElMessage.success('已结清')
  load()
}

async function doReslice() {
  const params = resliceAdvanced.value
    ? { preset: null, advanced: { ...advancedParams } }
    : { preset: resliceParams.value.preset }
  await api.post(`/orders/${id}/reslice`, {
    params, material_id: order.value.material_id, color: order.value.color,
  })
  ElMessage.success('已重新切片，提交 Val2 审核')
  resliceDialog.value = false
  load()
}

function canAct() {
  const s = order.value?.status
  const lastIssue = order.value?.issues?.at(-1)
  const isModel = lastIssue?.type === 'MODEL'
  return {
    // 参数问题 → 调参重切（§10.1 / §7.6）
    reslice: s === 'val2_failed' ? !isModel : (s === 'rework' && lastIssue?.type === 'PARAMETER'),
    // 模型问题 → 更换/重新上传模型，重走 Val1（§10.3 / §7.6）
    changeModel: (s === 'val2_failed' || s === 'rework') && isModel,
    // 设备问题 → 等待负责人安排半价重打（§10.2）
    machineWait: s === 'rework' && lastIssue?.type === 'MACHINE',
    feedback: s === 'val3_pending',
    settle: s === 'settlement',
    workspace: ['draft', 'modeling', 'val1_failed'].includes(s),
    appeal: s === 'val1_appeal' && !order.value?.appeal,
  }
}

onMounted(() => { app.loadMeta(); load() })
</script>

<template>
  <div class="page" v-loading="loading">
    <template v-if="order">
      <div style="display: flex; justify-content: space-between; align-items: start">
        <div>
          <h1 class="page-title">需求 O{{ order.id }} · {{ order.name }}</h1>
          <p class="page-sub">
            活动内编号 O{{ order.id }} · 创建于 {{ order.created_at?.slice(0, 16) }}
            <StatusTag :status="order.status" />
          </p>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
          <el-button v-if="canAct().workspace" type="primary" @click="router.push(`/create/${id}/workspace`)">继续摆放</el-button>
          <el-button v-if="canAct().changeModel" type="warning" @click="router.push(`/create?id=${id}`)">更换 / 重新上传模型（重走 Val1）</el-button>
          <el-alert v-if="canAct().machineWait" type="info" :closable="false" style="padding: 6px 12px"
                    title="设备问题：等待负责人处理设备后安排半价重打（§10.2）" />
          <el-button v-if="canAct().settle" type="success" @click="settle">结清（计入活动账单）</el-button>
          <el-button v-if="canAct().reslice" type="warning" @click="resliceDialog = true">调整参数重新切片</el-button>
        </div>
      </div>

      <!-- 主链状态轴（签名元素） -->
      <div class="card" style="margin-bottom: 20px">
        <ChainView :status="order.status" />
      </div>

      <div style="display: grid; grid-template-columns: 1.6fr 1fr; gap: 20px">
        <!-- 左：时间轴 + 打印任务 -->
        <div style="display: flex; flex-direction: column; gap: 20px">
          <div class="card">
            <h3 style="margin: 0 0 14px">状态时间轴（§12.2 两级状态机）</h3>
            <div class="tl">
              <div v-for="(t, i) in order.timeline" :key="i" class="tl-item">
                <div class="tl-time">{{ t.t }} · {{ t.status }}</div>
                <div class="tl-note">{{ t.note }}</div>
              </div>
            </div>
          </div>

          <div class="card" v-if="order.print_jobs?.length">
            <h3 style="margin: 0 0 12px">打印任务（§3.5：一个需求可多次打印）</h3>
            <div v-for="j in order.print_jobs" :key="j.id" style="border: 1px solid var(--line); border-radius: 8px; padding: 12px; margin-bottom: 10px">
              <div style="display: flex; justify-content: space-between">
                <b>打印 #{{ j.seq }}</b>
                <span class="tag" :class="j.status === 'done' ? 'tag-pass' : j.status === 'printing' ? 'tag-warn' : 'tag-ink'">
                  {{ { queued: '排队中', printing: '打印中', done: '已完成', blocked: '待检验耗材' }[j.status] }}
                </span>
              </div>
              <div class="mono muted" style="font-size: 12px; margin-top: 4px">
                {{ j.printer_id || '未分配打印机' }} · 预计 {{ Math.round(j.est_time_sec / 60) }}min /
                {{ j.est_weight_g }}g · {{ j.actual_weight_g ? '实际 ' + j.actual_weight_g + 'g' : '' }}
              </div>
              <el-progress v-if="j.status === 'printing'" :percentage="Math.round((j.progress || 0) * 100)" :stroke-width="8" style="margin-top: 8px" />
              <div class="muted" style="font-size: 12.5px; margin-top: 4px">{{ j.note }}</div>
            </div>
          </div>

          <!-- Val3 反馈 -->
          <div class="card" v-if="canAct().feedback">
            <h3 style="margin: 0 0 8px">Val3 实物验收（§9）</h3>
            <p class="muted" style="margin: 0 0 10px; font-size: 13px">打印已完成，负责人验收后你可对实物结果补充反馈：</p>
            <el-input v-model="feedbackText" type="textarea" :rows="2" placeholder="如：整体满意，但表面有拉丝…" />
            <el-button type="primary" style="margin-top: 8px" @click="sendFeedback">提交反馈</el-button>
          </div>
        </div>

        <!-- 右：信息 + 审核 + 费用 -->
        <div style="display: flex; flex-direction: column; gap: 20px">
          <div class="card">
            <h3 style="margin: 0 0 10px">需求信息</h3>
            <el-descriptions :column="1" size="small" border>
              <el-descriptions-item label="模型">{{ order.model_name || '—' }}（v{{ order.model_version_id }}）</el-descriptions-item>
              <el-descriptions-item label="耗材">{{ material?.name || order.material_id }} · {{ order.color }}</el-descriptions-item>
              <el-descriptions-item label="参数">
                {{ order.params?.preset ? `${order.params.preset} 档` : `${order.params?.layer_height}mm / 填充${order.params?.infill}%` }}
              </el-descriptions-item>
              <el-descriptions-item label="尺寸">
                {{ order.geometry?.bbox ? order.geometry.bbox.join(' × ') + ' mm' : '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="自备耗材">{{ order.self_filament ? (order.filament_approved ? '已检验合格' : '待检验（§16.3）') : '平台耗材' }}</el-descriptions-item>
            </el-descriptions>
          </div>

          <div class="card" v-if="order.reviews?.length">
            <h3 style="margin: 0 0 10px">审核记录（§13.3）</h3>
            <div v-for="(r, i) in order.reviews" :key="i" style="border-left: 3px solid var(--line); padding: 4px 0 4px 10px; margin-bottom: 6px">
              <div><b>{{ r.stage.toUpperCase() }}</b> · {{ r.result }} <span class="muted">— {{ r.reviewer }}</span></div>
              <div class="muted" style="font-size: 12.5px">{{ r.note }} · {{ r.at?.slice(0, 16) }}</div>
            </div>
          </div>

          <div class="card" v-if="order.issues?.length">
            <h3 style="margin: 0 0 10px">问题记录（§12.3 与状态分离）</h3>
            <el-tag v-for="i in order.issues" :key="i.id" type="danger" effect="plain" style="margin: 0 6px 6px 0">
              {{ issueLabels[i.type] }}：{{ i.description }}
            </el-tag>
          </div>

          <div class="card">
            <h3 style="margin: 0 0 10px">费用明细（§11 / §13.5 流水）</h3>
            <el-table :data="order.ledger" size="small">
              <el-table-column label="类别" width="80">
                <template #default="{ row }">
                  {{ { filament: '耗材', maintenance: '维护', api: 'API' }[row.kind] }}
                </template>
              </el-table-column>
              <el-table-column prop="reason" label="说明" />
              <el-table-column label="金额" width="90">
                <template #default="{ row }"><span class="amount">¥{{ row.amount.toFixed(2) }}</span></template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!order.ledger?.length" description="尚无费用流水（Val3 通过后核算）" :image-size="50" />
            <div v-if="order.cost?.total" style="display: flex; justify-content: space-between; margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--line)">
              <span class="muted">合计（耗材 + 维护 + API）</span>
              <span class="amount" style="font-size: 16px; color: var(--accent)">¥{{ order.cost.total.toFixed(2) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 重切对话框 -->
      <el-dialog v-model="resliceDialog" title="调整参数重新切片（§7.6 / §10.1）" width="440px">
        <el-form label-position="top">
          <el-form-item label="参数模式">
            <el-radio-group v-model="resliceAdvanced">
              <el-radio-button :value="false">标准档</el-radio-button>
              <el-radio-button :value="true">进阶手动</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <template v-if="!resliceAdvanced">
            <el-form-item label="标准档">
              <el-select v-model="resliceParams.preset" style="width: 100%">
                <el-option v-for="p in app.meta?.presets || []" :key="p.id" :value="p.id" :label="`${p.name}（${p.layer_height}mm/${p.infill}%）`" />
              </el-select>
            </el-form-item>
          </template>
          <template v-else>
            <AdvancedParamsForm v-model="advancedParams" />
          </template>
        </el-form>
        <template #footer>
          <el-button @click="resliceDialog = false">取消</el-button>
          <el-button type="primary" @click="doReslice">重新切片并提交 Val2</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>
