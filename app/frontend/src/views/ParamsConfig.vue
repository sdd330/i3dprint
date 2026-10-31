<script setup>
// 参数配置页（§4.2）：耗材/参数 + 3D 预览 + 提交 Val1 → 切片 → G-code 预览
// 与摆放工作区分离：摆放见 /create/:id/workspace，这里复用其保存的 placement
import { ref, reactive, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { api } from '@/api'
import { useAppStore } from '@/stores'
import { loadModelIntoGroup, applyPlacement, groupBBox } from '@/three/models'
import AdvancedParamsForm from '@/components/AdvancedParamsForm.vue'
import LayerPreview from '@/components/LayerPreview.vue'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const orderId = Number(route.params.id)
const order = ref(null)
const container = ref(null)
const loading = ref(true)
const submitting = ref(false)

// —— 3D 预览 ——
let scene, camera, renderer, controls, modelGroup, frameId
const BUILD = 256
const previewBBox = ref(null)

function initPreview() {
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xF6F2FB)
  camera = new THREE.PerspectiveCamera(45, 1, 1, 5000)
  camera.position.set(220, 220, 300)
  renderer = new THREE.WebGLRenderer({ antialias: true })
  container.value.appendChild(renderer.domElement)
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.target.set(0, 80, 0)
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd8d2c4, 1.1))
  const dir = new THREE.DirectionalLight(0xffffff, 1.4)
  dir.position.set(150, 300, 120)
  scene.add(dir)
  const box = new THREE.Mesh(
    new THREE.BoxGeometry(BUILD, BUILD, BUILD),
    new THREE.MeshBasicMaterial({ color: 0x2b6cb0, transparent: true, opacity: 0.04, side: THREE.DoubleSide })
  )
  box.position.set(0, BUILD / 2, 0)
  scene.add(box)
  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(BUILD, BUILD, BUILD)),
    new THREE.LineBasicMaterial({ color: 0x9fb4b8, transparent: true, opacity: 0.5 })
  )
  edges.position.set(0, BUILD / 2, 0)
  scene.add(edges)
  scene.add(new THREE.GridHelper(BUILD, 8, 0xD3C6E8, 0xE9E2F5))
  modelGroup = new THREE.Group()
  scene.add(modelGroup)
  const resize = () => {
    const w = container.value.clientWidth, h = container.value.clientHeight
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
  }
  resize()
  window.addEventListener('resize', resize)
  const animate = () => {
    frameId = requestAnimationFrame(animate)
    controls.update()
    renderer.render(scene, camera)
  }
  animate()
}

async function loadOrder() {
  const d = await api.get(`/orders/${orderId}`)
  order.value = d.order
  if (order.value.model_id) {
    await loadModelIntoGroup(d.order, modelGroup)
    applyPlacement(modelGroup, order.value.placement)
    // 预览坐标：模型可能未吸底，预览不需要；bbox 按摆放后计算
    previewBBox.value = groupBBox(modelGroup)
  }
  loading.value = false
}

// —— 参数表单 ——
const form = reactive({ material: 'pla', color: '#E8602C', preset: 'standard', selfFilament: false })
const advanced = ref(false)
// 进阶参数默认值 = X1C 标准档基准（OrcaSlicer 字段）
const advancedParams = reactive({ layer_height: 0.2, initial_layer_print_height: 0.2, wall_loops: 2, top_shell_layers: 4, bottom_shell_layers: 3, infill_density: 20, infill_pattern: 'grid', outer_wall_speed: 200, inner_wall_speed: 300, sparse_infill_speed: 270, travel_speed: 500, initial_layer_speed: 50, nozzle_temperature: 220, initial_layer_print_temperature: 220, bed_temperature: 65, initial_layer_bed_temperature: 65, enable_support: 'auto', support_type: 'normal(auto)', support_threshold_angle: 30, retraction_length: 0.8, retraction_speed: 30, z_hop: 0.4, max_volumetric_speed: 21 })
watch(() => form.material, (m) => {
  const mat = app.meta?.materials?.find(x => x.id === m)
  if (mat?.colors?.length) form.color = mat.colors[0]
}, { immediate: true })

// —— 切片预览（§6.2：预计时间/重量/层数来自切片器输出；进阶可见 G-code 预览）——
const sliceVisible = ref(false)
const sliceResult = ref(null)
const val2auto = ref(null)
const queueInfo = ref(null)  // 云端切片队列（active/waiting/max）
let queueTimer = null

async function pollQueue() {
  try { queueInfo.value = await api.get('/slicing/queue') } catch { /* 忽略 */ }
}

async function submit() {
  if (!previewBBox.value) return ElMessage.warning('模型预览未加载')
  submitting.value = true
  queueInfo.value = null
  await pollQueue()
  queueTimer = setInterval(pollQueue, 1500)  // 切片期间轮询队列，展示排队
  const params = advanced.value
    ? { preset: null, advanced: { ...advancedParams } }
    : { preset: form.preset }
  try {
    const d = await api.post(`/orders/${orderId}/slice`, {
      material_id: form.material,
      color: form.color,
      params,
      self_filament: form.selfFilament,
    })
    order.value = d.order
    sliceResult.value = d.slice || null
    val2auto.value = d.val2auto || null
    sliceVisible.value = true
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    clearInterval(queueTimer)
    queueTimer = null
    submitting.value = false
  }
}

function goDetail() {
  sliceVisible.value = false
  router.push(`/orders/${orderId}`)
}
async function confirmSlice() {
  try {
    await api.post(`/orders/${orderId}/confirm-slice`, {})
    sliceVisible.value = false
    ElMessage.success('已提交 Val2 人工审核')
    router.push(`/orders/${orderId}`)
  } catch (e) {
    ElMessage.error(e.message)
  }
}
async function backAdjust() {
  try {
    await api.post(`/orders/${orderId}/back-to-modeling`, {})
    sliceVisible.value = false
    ElMessage.success('已返回摆放调整')
    router.push(`/create/${orderId}/workspace`)
  } catch (e) {
    ElMessage.error(e.message)
  }
}

const materialOf = computed(() => app.meta?.materials?.find(m => m.id === form.material))

onMounted(async () => {
  await app.loadMeta()
  initPreview()
  loadOrder()
})
onBeforeUnmount(() => {
  cancelAnimationFrame(frameId)
  renderer?.dispose()
})
</script>

<template>
  <div style="height: calc(100vh - 58px); display: flex">
    <!-- 3D 预览 -->
    <div ref="container" style="flex: 1; position: relative; background: var(--paper)">
      <div style="position: absolute; top: 12px; left: 14px; z-index: 5; background: rgba(255,255,255,.85);
                  border-radius: 8px; padding: 8px 12px; font-size: 12.5px; box-shadow: var(--shadow)">
        参数配置预览 · 打印平台 <b>256×256×256mm</b>
        <div class="mono muted" style="margin-top: 2px" v-if="previewBBox">尺寸：{{ previewBBox.join(' × ') }} mm</div>
      </div>
      <div v-loading="loading" :style="{ position: 'absolute', inset: 0, zIndex: 4, pointerEvents: loading ? 'auto' : 'none' }" />
    </div>

    <!-- 右侧：耗材 / 参数 -->
    <div style="width: 340px; border-left: 1px solid var(--line); background: var(--card); overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 14px">
      <div>
        <div style="font-weight: 700">需求 O{{ orderId }} · 参数配置（§4.2）</div>
        <div class="muted" style="font-size: 12.5px">摆放已锁定（{{ order?.placement?.rotation?.join('° ') }}° / ×{{ order?.placement?.scale }}），预览为摆放后状态</div>
      </div>

      <el-form label-position="top" size="small">
        <el-form-item label="耗材材料">
          <el-select v-model="form.material" style="width: 100%">
            <el-option v-for="m in app.meta?.materials || []" :key="m.id" :value="m.id"
                       :label="`${m.name} · ${m.price_per_g} 元/g ×${m.coeff}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="颜色">
          <div style="display: flex; gap: 8px; flex-wrap: wrap">
            <span v-for="c in ['#E8602C','#2B6CB0','#2F855A','#D69E2E','#38B2AC','#9F7AEA','#F687B3','#CBD5E0']"
                  :key="c" @click="form.color = c"
                  :style="{ width: 26, height: 26, borderRadius: 7, background: c, cursor: 'pointer', border: form.color === c ? '3px solid #23262b' : '2px solid #fff', boxShadow: '0 0 0 1px var(--line)' }" />
          </div>
        </el-form-item>
        <el-form-item label="打印参数">
          <template v-if="!advanced">
            <el-radio-group v-model="form.preset">
              <el-radio v-for="p in app.meta?.presets || []" :key="p.id" :value="p.id">
                {{ p.name }}<span class="muted" style="font-size: 11.5px">（{{ p.layer_height }}mm/{{ p.infill }}%）</span>
              </el-radio>
            </el-radio-group>
            <div style="width: 100%">
              <el-link type="primary" @click="advanced = true">进阶手动设置 →</el-link>
            </div>
          </template>
          <template v-else>
            <AdvancedParamsForm v-model="advancedParams" />
            <div style="width: 100%; margin-top: 4px">
              <el-link type="primary" @click="advanced = false">← 回到标准档</el-link>
            </div>
          </template>
        </el-form-item>
        <el-form-item>
          <el-switch v-model="form.selfFilament" active-text="自备耗材（§16.3）" />
        </el-form-item>
      </el-form>

      <el-button type="primary" size="large" :loading="submitting" @click="submit">
        {{ submitting ? '云端切片中…' : '提交切片（云端 OrcaSlicer）' }}
      </el-button>
      <div v-if="submitting && queueInfo" class="muted mono" style="text-align: center; font-size: 12px">
        执行中 {{ queueInfo.active }}/{{ queueInfo.max }}
        <span v-if="queueInfo.waiting"> · 队列前还有 {{ queueInfo.waiting }} 个</span>
        （并发限流，自动排队）
      </div>
      <el-button @click="router.push(`/create/${orderId}/workspace`)">← 返回摆放</el-button>
    </div>

    <!-- 切片预览（§6.2） -->
    <el-dialog v-model="sliceVisible" width="620px" :close-on-click-modal="false">
      <template #header><b>切片预览（§6）</b></template>
      <div v-if="sliceResult" style="display: flex; flex-direction: column; gap: 12px">
        <el-alert type="info" :closable="false" title="切片完成，请预览后确认（§6）：满意则提交 Val2 审核，不满意可返回调整"
                  :description="`切片器：${sliceResult.slicer} · 预计 ${Math.round(sliceResult.est_time_sec / 60)}min / ${sliceResult.est_weight_g}g`" />
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="层数">{{ sliceResult.gcode?.layers }}</el-descriptions-item>
          <el-descriptions-item label="路径长度">{{ sliceResult.gcode?.path_km }} km</el-descriptions-item>
          <el-descriptions-item label="支撑">{{ sliceResult.supports === 'auto' ? '树形（自动）' : '无' }}</el-descriptions-item>
          <el-descriptions-item label="Val2 自动检查">{{ val2auto?.result }}</el-descriptions-item>
          <el-descriptions-item label="数据来源" :span="2">{{ sliceResult.source === 'mock' ? '模拟估算（未接切片器）' : 'OrcaSlicer 输出' }}</el-descriptions-item>
        </el-descriptions>
        <el-collapse>
          <el-collapse-item title="进阶：逐层路径预览（§6.2 / §7.3，真实切片路径）" name="gcode">
            <LayerPreview :order-id="orderId" />
          </el-collapse-item>
        </el-collapse>
        <div style="display: flex; gap: 8px">
          <el-button style="flex: 1" @click="backAdjust">← 返回调整</el-button>
          <el-button type="primary" style="flex: 1" @click="confirmSlice">预览满意，提交审核 →</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>
