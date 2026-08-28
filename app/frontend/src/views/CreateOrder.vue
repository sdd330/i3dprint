<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { useAppStore } from '@/stores'

const router = useRouter()
const app = useAppStore()
const order = ref(null)
const creating = ref(false)
const showPreset = ref(true)
const fileInput = ref(null)

const models = [
  { kind: 'vase', name: '桌面小花瓶', desc: '螺旋纹小花瓶，适合桌面摆放', emoji: '🏺' },
  { kind: 'robot', name: '可动小机器人', desc: '关节可动的小机器人摆件', emoji: '🤖' },
  { kind: 'stand', name: '手机支架', desc: '桌面手机支架，横竖屏均可', emoji: '📱' },
  { kind: 'penholder', name: '多功能笔筒', desc: '六边形笔筒，可放文具与手机', emoji: '🖊️' },
  { kind: 'spinner', name: '指尖陀螺', desc: '解压指尖陀螺（薄壁款有风险）', emoji: '🌀' },
]
const materials = computed(() => app.meta?.materials || [])
const presets = computed(() => app.meta?.presets || [])
const selected = ref({ material: 'pla', color: '#E8602C', preset: 'standard' })

const campaign = computed(() => app.meta?.campaign)

onMounted(async () => {
  await app.loadMeta()
  const { id } = router.currentRoute.value.query
  if (id) {
    order.value = (await api.get(`/orders/${id}`)).order
  }
})

async function createOrder() {
  creating.value = true
  try {
    const d = await api.post('/orders', {})
    order.value = d.order
    ElMessage.success('需求已创建，接下来选择模型')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    creating.value = false
  }
}

async function selectPreset(kind) {
  const d = await api.post(`/orders/${order.value.id}/select-model`, { preset_kind: kind })
  order.value = d.order
  gotoWorkspace()
}

async function onFile(e) {
  const file = e.target.files[0]
  if (!file) return
  const d = await api.upload(`/orders/${order.value.id}/upload`, file)
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
    <p class="page-sub">活动「{{ campaign?.name }}」{{ campaign ? '· ' + campaign.status : '' }} · 上传模型或从内置演示模型开始</p>

    <!-- 步骤 1：创建 -->
    <el-card v-if="!order" shadow="never">
      <el-empty description="先创建一个空的打印需求，然后选择模型进入摆放工作区">
        <el-button type="primary" :loading="creating" @click="createOrder">创建需求</el-button>
      </el-empty>
    </el-card>

    <!-- 步骤 2：选模型 -->
    <template v-else-if="['draft', 'modeling', 'val1_failed'].includes(order.status)">
      <div style="display: flex; gap: 12px; margin-bottom: 16px; align-items: center">
        <el-tag type="success" effect="plain" round>需求 O{{ order.id }} · {{ order.name }}</el-tag>
        <el-radio-group v-model="showPreset" size="small">
          <el-radio-button :value="true">内置演示模型</el-radio-button>
          <el-radio-button :value="false">上传 STL / OBJ</el-radio-button>
        </el-radio-group>
        <span class="muted" style="font-size: 12.5px">没有模型？去 <router-link to="/ai">AI 建模</router-link> 生成后自动填充</span>
      </div>

      <div v-if="showPreset" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px">
        <div v-for="m in models" :key="m.kind" class="card" style="cursor: pointer; padding: 16px; transition: transform .15s"
             @mouseenter="$event.target.style.transform = 'translateY(-2px)'"
             @mouseleave="$event.target.style.transform = ''" @click="selectPreset(m.kind)">
          <div style="font-size: 34px">{{ m.emoji }}</div>
          <div style="font-weight: 700; margin-top: 6px">{{ m.name }}</div>
          <div class="muted" style="font-size: 12.5px">{{ m.desc }}</div>
        </div>
      </div>
      <div v-else class="card" style="text-align: center; padding: 40px">
        <input ref="fileInput" type="file" accept=".stl,.obj" style="display: none" @change="onFile" />
        <el-button type="primary" @click="fileInput.click()">选择 STL / OBJ 文件</el-button>
        <div class="muted" style="margin-top: 8px; font-size: 12.5px">上传后自动进入摆放工作区；Val1 会用服务端 trimesh 做真实几何校验</div>
      </div>
    </template>

    <!-- 其他状态提示 -->
    <el-card v-else shadow="never">
      <el-result icon="info" :title="`该需求当前状态：${order.status}`">
        <el-button type="primary" @click="router.push(`/orders/${order.id}`)">查看订单追踪</el-button>
      </el-result>
    </el-card>
  </div>
</template>
