<script setup>
// 逐层路径预览（§7.3 每层打印路径 / §6.2 G-code 预览）
// 数据源：切片产物 plate_1.gcode 解析出的每层挤出路径（后端 API）
import { ref, watch, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const props = defineProps({ orderId: { type: Number, required: true } })
const loading = ref(false)
const data = ref(null)
const current = ref(0)
const canvasRef = ref(null)

async function load() {
  loading.value = true
  try {
    data.value = await api.get(`/orders/${props.orderId}/layer-preview`)
    current.value = Math.floor((data.value.count || 1) / 2) // 默认中间层
    draw()
  } catch (e) {
    ElMessage.warning(e.message)
  } finally {
    loading.value = false
  }
}

const layerHeight = computed(() => data.value?.layer_height || 0.2)

function draw() {
  const canvas = canvasRef.value
  if (!canvas || !data.value?.layers?.length) return
  const layer = data.value.layers[current.value]
  const ctx = canvas.getContext('2d')
  const W = canvas.width, H = canvas.height
  ctx.clearRect(0, 0, W, H)
  ctx.fillStyle = '#fbf9f4'
  ctx.fillRect(0, 0, W, H)
  // 平台 256×256 映射
  const pad = 18
  const scale = Math.min((W - pad * 2) / 256, (H - pad * 2) / 256)
  const ox = (W - 256 * scale) / 2, oy = (H - 256 * scale) / 2
  ctx.strokeStyle = '#e6e1d8'
  ctx.strokeRect(ox, oy, 256 * scale, 256 * scale)
  // 挤出路径
  ctx.strokeStyle = '#e8602c'
  ctx.lineWidth = 1.1
  for (const path of layer.paths || []) {
    if (path.length < 2) continue
    ctx.beginPath()
    path.forEach(([x, y], i) => {
      const px = ox + x * scale, py = oy + y * scale
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)
    })
    ctx.stroke()
  }
}

function changeLayer(v) {
  current.value = v
  draw()
}

watch(current, () => draw())
onMounted(() => { setTimeout(load, 100) })
</script>

<template>
  <div v-loading="loading">
    <div v-if="data?.layers?.length" style="display: flex; gap: 16px">
      <!-- 逐层图 -->
      <canvas ref="canvasRef" width="420" height="420" style="border: 1px solid var(--line); border-radius: 8px; max-width: 100%" />
      <!-- 层控制 -->
      <div style="flex: 1; min-width: 180px">
        <div style="display: flex; justify-content: space-between; align-items: center">
          <b>第 {{ current + 1 }} / {{ data.count }} 层</b>
          <span class="mono muted" style="font-size: 12px">Z = {{ data.layers[current]?.z.toFixed(2) }}mm</span>
        </div>
        <el-slider v-model="current" :min="0" :max="data.count - 1" :step="1" @input="changeLayer" style="margin-top: 12px" />
        <div class="muted" style="font-size: 12px; margin-top: 6px">
          层高 {{ layerHeight }}mm · 橙色为挤出路径（含外壁/内壁/填充/支撑）
        </div>
        <div class="muted" style="font-size: 12px; margin-top: 4px">
          数据源：OrcaSlicer 切片产物 plate_1.gcode（§6.2），真实打印路径
        </div>
      </div>
    </div>
    <el-empty v-else-if="!loading" description="暂无逐层数据（未切片或产物缺失）" :image-size="60" />
  </div>
</template>
