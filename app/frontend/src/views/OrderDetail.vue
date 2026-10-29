<script setup>
// 订单追踪（时间轴）：状态展示 + 按状态给出下一步动作
// 2026-10：Val1 无自动退回（标记 → 人工复核）；在线切片/Val2 暂缓；收费信息暂时隐去
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { useAppStore } from '@/stores'
import StatusTag from '@/components/StatusTag.vue'
import ChainView from '@/components/ChainView.vue'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const order = ref(null)
const loading = ref(true)
const feedbackText = ref('')

const id = Number(route.params.id)
const billingVisible = computed(() => app.billingVisible)
const material = computed(() => app.materials.find(m => m.id === order.value?.material_id))
const issueLabels = computed(() => ({
  PARAMETER: '参数问题', MACHINE: '设备问题', MODEL: '模型问题',
  MACHINE_LIMIT: '设备能力上限', CONTENT: '内容不合规', OTHER: '其他',
}))
const val1 = computed(() => order.value?.val1)
const flagged = computed(() => val1.value?.flagged_items || [])
const manifest = computed(() => order.value?.manifest)
const lastIssue = computed(() => order.value?.issues?.at(-1))

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
  await ElMessageBox.confirm('确认该需求已完成（负责人已验收并交付）？', '确认完成')
  await api.post(`/orders/${id}/settle`, {})
  ElMessage.success('已完成')
  load()
}

function canAct() {
  const s = order.value?.status
  const isParam = ['PARAMETER', 'OTHER'].includes(lastIssue.value?.type)
  const isModel = lastIssue.value?.type === 'MODEL'
  const isMachine = lastIssue.value?.type === 'MACHINE'
  return {
    workspace: ['draft', 'modeling', 'val1_failed'].includes(s),
    // 填写/修改打印需求（材料 / 强度 / 进阶参数）
    printRequirement: s === 'print_config' || (s === 'rework' && isParam),
    waitingReview: s === 'val1_review',
    changeModel: s === 'val1_failed' || (s === 'rework' && isModel),
    machineWait: s === 'rework' && isMachine,
    feedback: s === 'val3_pending',
    settle: s === 'settlement',
  }
}

onMounted(() => { if (!app.meta) app.loadMeta(); load() })
</script>

<template>
  <div class="page" v-loading="loading">
    <template v-if="order">
      <div style="display: flex; justify-content: space-between; align-items: start; gap: 12px; flex-wrap: wrap">
        <div>
          <h1 class="page-title">需求 O{{ order.id }} · {{ order.name }}</h1>
          <p class="page-sub">
            活动内编号 O{{ order.id }} · 创建于 {{ order.created_at?.slice(0, 16) }}
            <StatusTag :status="order.status" />
          </p>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
          <el-button v-if="canAct().printRequirement" type="primary" @click="router.push(`/create/${id}/print-req`)">
            {{ order.status === 'rework' ? '调整打印需求' : '填写打印需求' }}
          </el-button>
          <el-button v-if="canAct().workspace" type="primary" @click="router.push(`/create/${id}/workspace`)">继续摆放</el-button>
          <el-button v-if="canAct().changeModel" type="warning" @click="router.push(`/create?id=${id}`)">
            更换 / 重新上传模型（重走 Val1）
          </el-button>
          <el-alert v-if="canAct().waitingReview" type="warning" :closable="false" style="padding: 6px 12px"
                    title="Val1 已标记潜在问题，负责人正在人工复核（不需要你重做）" />
          <el-alert v-if="canAct().machineWait" type="info" :closable="false" style="padding: 6px 12px"
                    title="设备问题：负责人处理设备后重新打印（§10.2）" />
          <el-button v-if="canAct().settle" type="success" @click="settle">确认完成</el-button>
        </div>
      </div>

      <!-- 主链状态轴（签名元素） -->
      <div class="card" style="margin-bottom: 20px">
        <ChainView :status="order.status" />
      </div>

      <div style="display: grid; grid-template-columns: 1.6fr 1fr; gap: 20px">
        <!-- 左：时间轴 + 打印清单 + 打印任务 -->
        <div style="display: flex; flex-direction: column; gap: 20px">
          <!-- Val1 标记项 -->
          <div class="card" v-if="val1">
            <div style="display: flex; justify-content: space-between; align-items: center">
              <h3 style="margin: 0">Val1 模型审核</h3>
              <el-tag :type="val1.flagged ? 'warning' : 'success'" effect="plain">
                {{ val1.result }}{{ val1.flagged ? ` · 标记 ${flagged.length} 项` : '' }}
              </el-tag>
            </div>
            <p class="muted" style="margin: 8px 0 0; font-size: 13px">{{ val1.summary }}</p>
            <div v-if="flagged.length" style="margin-top: 8px">
              <el-tag v-for="f in flagged" :key="f.id" :type="f.level === 'fail' ? 'danger' : 'warning'"
                      effect="plain" style="margin: 0 6px 6px 0">
                {{ f.name }}：{{ f.message }}
              </el-tag>
              <div class="muted" style="font-size: 12.5px">
                这些项目由负责人人工复核决定是否放行——系统不会自动退回你的需求。
              </div>
            </div>
          </div>

          <!-- 打印清单 -->
          <div class="card" v-if="manifest">
            <h3 style="margin: 0 0 10px">打印清单（执行打印的依据）</h3>
            <el-descriptions :column="2" size="small" border>
              <el-descriptions-item label="材料">{{ manifest.material?.name }}</el-descriptions-item>
              <el-descriptions-item label="颜色">{{ manifest.color }}</el-descriptions-item>
              <el-descriptions-item label="强度">{{ manifest.strength?.name }}</el-descriptions-item>
              <el-descriptions-item label="层高">{{ manifest.params?.layer_height }} mm</el-descriptions-item>
              <el-descriptions-item label="壁厚">{{ manifest.params?.wall_loops }} 圈</el-descriptions-item>
              <el-descriptions-item label="填充">{{ manifest.params?.infill_density }}%（{{ manifest.params?.infill_pattern }}）</el-descriptions-item>
              <el-descriptions-item label="尺寸">{{ (manifest.bbox || []).join(' × ') }} mm</el-descriptions-item>
              <el-descriptions-item label="预估">{{ manifest.estimate?.weight_g }}g / {{ Math.round((manifest.estimate?.time_sec || 0) / 60) }}min</el-descriptions-item>
            </el-descriptions>
            <div v-if="manifest.operator_note" class="muted" style="font-size: 12.5px; margin-top: 8px">
              备注给负责人：{{ manifest.operator_note }}
            </div>
            <div class="muted" style="font-size: 12px; margin-top: 6px">
              预估值为几何量估算（当前版本不做在线切片），实际耗材与时长以切片器结果为准。
            </div>
          </div>

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
                  {{ { queued: '清单中待打印', printing: '打印中', done: '已完成', blocked: '待检验耗材' }[j.status] }}
                </span>
              </div>
              <div class="mono muted" style="font-size: 12px; margin-top: 4px">
                {{ j.printer_id || '未分配打印机' }} · 预估 {{ Math.round(j.est_time_sec / 60) }}min /
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

        <!-- 右：信息 + 审核 + 问题记录（+ 费用） -->
        <div style="display: flex; flex-direction: column; gap: 20px">
          <div class="card">
            <h3 style="margin: 0 0 10px">需求信息</h3>
            <el-descriptions :column="1" size="small" border>
              <el-descriptions-item label="模型">{{ order.model_name || '—' }}（v{{ order.model_version_id }}）</el-descriptions-item>
              <el-descriptions-item label="材料">
                {{ material?.name || order.material_id }}
                <span v-if="order.manifest?.color_name"> · {{ order.manifest.color_name }}</span>
                <span class="mono muted" style="font-size: 11.5px">{{ order.color }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="强度">{{ order.params?.strength_name || '待选择' }}</el-descriptions-item>
              <el-descriptions-item label="参数">
                <template v-if="order.params">
                  {{ order.params.layer_height }}mm 层高 / 壁厚 {{ order.params.wall_loops }} 圈 / 填充 {{ order.params.infill_density }}%
                </template>
                <template v-else>待选择</template>
              </el-descriptions-item>
              <el-descriptions-item label="尺寸">
                {{ order.geometry?.bbox ? order.geometry.bbox.join(' × ') + ' mm' : '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="自备耗材">
                {{ order.self_filament ? (order.filament_approved ? '已检验合格' : '待检验（§16.3）') : '平台耗材' }}
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <div class="card" v-if="order.reviews?.length">
            <h3 style="margin: 0 0 10px">审核记录（§13.3）</h3>
            <div v-for="(r, i) in order.reviews" :key="i" style="border-left: 3px solid var(--line); padding: 4px 0 4px 10px; margin-bottom: 6px">
              <div><b>{{ r.stage === 'val1' ? 'Val1' : r.stage === 'val3' ? 'Val3' : r.stage.toUpperCase() }}</b> · {{ r.result }} <span class="muted">— {{ r.reviewer }}</span></div>
              <div class="muted" style="font-size: 12.5px">{{ r.note }} · {{ r.at?.slice(0, 16) }}</div>
            </div>
          </div>

          <div class="card" v-if="order.issues?.length">
            <h3 style="margin: 0 0 10px">问题记录（§12.3 与状态分离）</h3>
            <el-tag v-for="i in order.issues" :key="i.id" type="danger" effect="plain" style="margin: 0 6px 6px 0">
              {{ issueLabels[i.type] }}：{{ i.description }}
            </el-tag>
          </div>

          <!-- 费用：当前版本隐去（flow.billing_visible=false） -->
          <div class="card" v-if="billingVisible">
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
    </template>
  </div>
</template>
