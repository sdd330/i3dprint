<script setup>
// AI 辅助建模（§14）：Tripo AI SDK（按用量计费）+ 就地打印体检（与 Val1 同源）
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { useAppStore } from '@/stores'

const app = useAppStore()
const router = useRouter()
// AI 建模入口暂时关闭（meta.flow.ai_modeling=false）；后端接口与计费逻辑保留
const aiEnabled = () => !!app.flow.ai_modeling
const desc = ref('给我生成一个手机支架，尺寸 8cm')
const generating = ref(false)
const result = ref(null)
const orderId = ref(null)

async function generate() {
  if (!aiEnabled()) return ElMessage.warning('AI 建模入口暂时关闭，请上传自己做的 STL / OBJ 模型')
  if (!desc.value.trim()) return
  generating.value = true
  try {
    result.value = await api.post('/ai/generate', { description: desc.value, size_cm: 8 })
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    generating.value = false
  }
}

async function fillToOrder() {
  // 自动填充到上传环节（§14.1）：创建订单并选择对应内置模型
  const d = await api.post('/orders', {})
  orderId.value = d.order.id
  await api.post(`/orders/${orderId.value}/select-model`, { preset_kind: result.value.kind })
  ElMessage.success('已填充到新需求，照走 Val1 与打印需求填写（不跳过）')
  router.push(`/create/${orderId.value}/workspace`)
}
</script>

<template>
  <div class="page" style="max-width: 860px">
    <h1 class="page-title">AI 辅助建模</h1>
    <p class="page-sub">独立功能（§14）· Tripo AI SDK 按用量计费 · 生成后自动打印体检，确认后下载或自动填充到上传环节</p>
    <el-alert v-if="!aiEnabled()" type="warning" :closable="false" show-icon style="margin-bottom: 14px"
              title="AI 建模入口暂时关闭"
              description="当前版本请自行建模后上传 STL / OBJ（可直接在「创建需求 → 上传模型」完成）。" />

    <div class="card">
      <el-input v-model="desc" type="textarea" :rows="3" placeholder="描述想要的模型，如：一个笔筒 / 机甲小人 / 手机支架…" />
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px">
        <span class="muted" style="font-size: 12.5px">提示：可写「花瓶」「机器人」「支架」「笔筒」「陀螺」触发内置演示模型</span>
        <el-button type="primary" :loading="generating" @click="generate">生成模型（按次计费）</el-button>
      </div>
    </div>

    <div v-if="result" class="card" style="margin-top: 20px">
      <h3 style="margin: 0 0 12px">生成结果 · {{ result.name }}</h3>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px">
        <div>
          <div class="muted" style="font-size: 13px">几何统计（服务端 trimesh 分析）</div>
          <el-descriptions :column="1" size="small" border style="margin-top: 8px">
            <el-descriptions-item label="尺寸">{{ result.stats.bbox.join(' × ') }} mm</el-descriptions-item>
            <el-descriptions-item label="体积">{{ result.stats.volume_cm3 }} cm³</el-descriptions-item>
            <el-descriptions-item label="表面积">{{ result.stats.surface_cm2 }} cm²</el-descriptions-item>
          </el-descriptions>
          <div style="margin-top: 12px; font-size: 12.5px" class="muted">
            用量：{{ result.usage.service }} · {{ result.usage.points }} 点 × {{ result.usage.unit_price }} 元/点
            = <b class="amount">¥{{ result.usage.amount.toFixed(2) }}</b>（入活动成本）
          </div>
        </div>
        <div>
          <div class="muted" style="font-size: 13px">就地打印体检（§14.2，与 Val1 同源）</div>
          <el-alert style="margin-top: 8px"
                    :type="result.report.result === '通过' ? 'success' : result.report.result === '警告' ? 'warning' : 'error'"
                    :title="`体检结果：${result.report.result}`" :description="result.report.summary" :closable="false" />
          <div v-for="i in result.report.items.filter(x => x.level !== 'pass')" :key="i.id"
               style="margin-top: 6px; font-size: 12.5px; color: var(--amber)">
            ⚠ {{ i.name }}：{{ i.message }}
          </div>
          <div style="display: flex; gap: 8px; margin-top: 14px">
            <el-button type="primary" @click="fillToOrder">自动填充到上传环节 →</el-button>
            <el-button>下载模型（演示）</el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
