<script setup>
// 创建打印需求：默认「上传模型」（含大文件进度条），可切换内置演示模型
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { useAppStore } from '@/stores'

const router = useRouter()
const app = useAppStore()
const order = ref(null)
const creating = ref(false)

const tab = ref('upload') // 默认上传模型
const uploadState = ref({ progress: 0, uploading: false, name: '', phase: 'transfer' })
const fileInput = ref(null)
const dragOver = ref(false)
const MAX_MB = 300

const models = [
  { kind: 'vase', name: '桌面小花瓶', desc: '螺旋纹小花瓶，适合桌面摆放', emoji: '🏺' },
  { kind: 'robot', name: '可动小机器人', desc: '关节可动的小机器人摆件', emoji: '🤖' },
  { kind: 'stand', name: '手机支架', desc: '桌面手机支架，横竖屏均可', emoji: '📱' },
  { kind: 'penholder', name: '多功能笔筒', desc: '六边形笔筒，可放文具与手机', emoji: '🖊️' },
  { kind: 'spinner', name: '指尖陀螺', desc: '解压指尖陀螺（薄壁款有风险）', emoji: '🌀' },
]
const campaign = computed(() => app.meta?.campaign)

onMounted(async () => {
  await app.loadMeta()
  const { id } = router.currentRoute.value.query
  if (id) order.value = (await api.get(`/orders/${id}`)).order
})

async function createOrder() {
  creating.value = true
  try {
    order.value = (await api.post('/orders', {})).order
    ElMessage.success('需求已创建，接下来选择模型')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    creating.value = false
  }
}

async function onFile(e) {
  const file = e.target.files[0]
  if (file) await upload(file)
  e.target.value = ''
}

async function upload(file) {
  if (uploadState.value.uploading) return // 上传/解析进行中，禁止再次上传
  if (file.size > MAX_MB * 1024 * 1024) return ElMessage.error(`文件超过 ${MAX_MB}MB 限制`)
  if (!order.value) await createOrder()
  uploadState.value = { progress: 0, uploading: true, name: file.name, phase: 'transfer' }
  try {
    const d = await api.upload(`/orders/${order.value.id}/upload`, file, (p) => {
      uploadState.value.progress = Math.round(p * 100)
      // 传输完成（100%）后进入后端解析阶段，给可视化提示
      if (p >= 1) uploadState.value.phase = 'parsing'
    })
    order.value = d.order
    uploadState.value.uploading = false
    ElMessage.success(`模型解析完成（${d.stats.face_count.toLocaleString()} 面）`)
    gotoWorkspace()
  } catch (err) {
    uploadState.value.uploading = false
    ElMessage.error(err.message)
  }
}

async function selectPreset(kind) {
  const d = await api.post(`/orders/${order.value.id}/select-model`, { preset_kind: kind })
  order.value = d.order
  gotoWorkspace()
}

function gotoWorkspace() {
  router.push(`/create/${order.value.id}/workspace`)
}
</script>

<template>
  <div class="page">
    <h1 class="page-title">创建打印需求</h1>
    <p class="page-sub">活动「{{ campaign?.name }}」{{ campaign ? '· ' + campaign.status : '' }}</p>

    <!-- 步骤 1：创建 -->
    <el-card v-if="!order" shadow="never">
      <el-empty description="先创建一个空的打印需求，然后选择模型进入摆放工作区">
        <el-button type="primary" :loading="creating" @click="createOrder">创建需求</el-button>
      </el-empty>
    </el-card>

    <!-- 步骤 2：选择模型来源 -->
    <template v-else-if="['draft', 'modeling', 'val1_failed'].includes(order.status)">
      <div style="display: flex; gap: 12px; margin-bottom: 14px; align-items: center">
        <el-tag type="success" effect="plain" round>需求 O{{ order.id }} · {{ order.name }}</el-tag>
        <span v-if="app.flow.ai_modeling" class="muted" style="font-size: 12.5px">没有现成模型？去 <router-link to="/ai">AI 建模</router-link> 生成后自动填充</span>
        <span v-else class="muted" style="font-size: 12.5px">没有现成模型？可先在其他软件里建模，导出 STL / OBJ 后上传</span>
      </div>

      <el-tabs v-model="tab" type="border-card">
        <!-- 上传模型（默认） -->
        <el-tab-pane name="upload">
          <template #label>
            <span style="font-weight: 700">📤 上传模型</span>
            <span class="muted" style="font-size: 12px; font-weight: 400">STL / OBJ（≤ {{ MAX_MB }}MB）</span>
          </template>
          <div
            :class="{ 'upload-zone': true, disabled: uploadState.uploading }"
            @click="!uploadState.uploading && fileInput.click()"
            @dragover.prevent="!uploadState.uploading && (dragOver = true)"
            @dragleave="dragOver = false"
            @drop.prevent="!uploadState.uploading && (dragOver = false) && onFile({ target: { files: $event.dataTransfer.files } })"
            :style="{
              border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--line)'}`,
              borderRadius: 12, padding: '46px 20px', textAlign: 'center', cursor: uploadState.uploading ? 'not-allowed' : 'pointer',
              background: dragOver ? 'var(--accent-soft)' : 'var(--bg)', transition: 'all .15s',
              opacity: uploadState.uploading ? 0.65 : 1, pointerEvents: uploadState.uploading ? 'none' : 'auto',
            }"
          >
            <input ref="fileInput" type="file" accept=".stl,.obj" style="display: none" @change="onFile" :disabled="uploadState.uploading" />
            <div style="font-size: 40px">📦</div>
            <div style="font-weight: 700; margin-top: 8px">点击选择或拖拽 STL / OBJ 文件到此处</div>
            <div class="muted" style="font-size: 12.5px; margin-top: 4px">
              支持最大 {{ MAX_MB }}MB · 上传后服务端 trimesh 自动解析几何（面数/封闭/悬垂/壁厚）
            </div>

            <!-- 上传进度条（传输 → 后端解析两阶段提示） -->
            <div v-if="uploadState.uploading" style="max-width: 460px; margin: 18px auto 0">
              <el-progress :percentage="uploadState.progress" :stroke-width="10"
                           :status="uploadState.phase === 'parsing' ? undefined : undefined" />
              <template v-if="uploadState.phase === 'parsing'">
                <el-alert type="info" :closable="false" style="margin-top: 10px"
                          title="模型已上传，正在解析几何（面数/封闭/壁厚/悬垂）…"
                          :description="'大文件（如 160MB）解析可能需要 10-60 秒，请勿关闭页面；超过 90 秒会自动提示。'" />
                <div class="muted mono" style="font-size: 12px; margin-top: 6px">{{ uploadState.name }} · 解析中</div>
              </template>
              <div v-else class="muted mono" style="font-size: 12px; margin-top: 6px">
                {{ uploadState.name }} · 上传 {{ uploadState.progress }}%
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 内置演示模型 -->
        <el-tab-pane name="preset">
          <template #label>
            <span style="font-weight: 700">🎲 内置演示模型</span>
            <span class="muted" style="font-size: 12px; font-weight: 400">快速体验</span>
          </template>
          <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px; padding: 6px 2px">
            <div v-for="m in models" :key="m.kind" class="card" style="cursor: pointer; padding: 14px; transition: transform .15s; margin: 0"
                 @mouseenter="$event.target.style.transform = 'translateY(-2px)'"
                 @mouseleave="$event.target.style.transform = ''" @click="selectPreset(m.kind)">
              <div style="font-size: 30px">{{ m.emoji }}</div>
              <div style="font-weight: 700; margin-top: 6px">{{ m.name }}</div>
              <div class="muted" style="font-size: 12.5px">{{ m.desc }}</div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- 其他状态提示 -->
    <el-card v-else shadow="never">
      <el-result icon="info" :title="`该需求当前状态：${order.status}`">
        <el-button type="primary" @click="router.push(`/orders/${order.id}`)">查看订单追踪</el-button>
      </el-result>
    </el-card>
  </div>
</template>
