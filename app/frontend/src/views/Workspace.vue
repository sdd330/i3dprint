<script setup>
// 模型摆放工作区（类 BambuStudio，§4.3）—— Three.js 本地渲染，不依赖 CDN
// 摆放约束（旋转/平移/缩放/阵列/吸底/自动摆放）作为 geometry.bbox 提交，Val1 以服务端 trimesh 为准
import { ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { api } from '@/api'
import { useAppStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const orderId = Number(route.params.id)
const order = ref(null)
const container = ref(null)
const loading = ref(true)
const submitting = ref(false)

// —— Three.js 场景 ——
let scene, camera, renderer, controls, modelGroup, buildBox, frameId
const BUILD = 256

function buildPreset(kind) {
  const g = new THREE.Group()
  const mat = () => new THREE.MeshStandardMaterial({ color: 0xe8602c, roughness: 0.55, metalness: 0.05 })
  const add = (geo, x = 0, y = 0, z = 0) => {
    const m = new THREE.Mesh(geo, mat())
    m.position.set(x, y, z)
    g.add(m)
  }
  if (kind === 'vase') {
    const pts = []
    for (let i = 0; i <= 24; i++) {
      const t = i / 24
      const r = 10 + 14 * Math.sin(Math.PI * t * 1.6) * (1 - t * 0.5)
      pts.push(new THREE.Vector2(r, t * 55))
    }
    add(new THREE.LatheGeometry(pts, 48))
  } else if (kind === 'robot') {
    add(new THREE.BoxGeometry(40, 50, 30), 0, 25, 0)
    add(new THREE.BoxGeometry(30, 24, 26), 0, 62, 0)
    add(new THREE.BoxGeometry(26, 40, 10), -33, 40, 0)
    add(new THREE.BoxGeometry(26, 40, 10), 33, 40, 0)
    const eye = new THREE.SphereGeometry(3, 16, 16)
    const eyem = new THREE.MeshStandardMaterial({ color: 0x23262b })
    ;[-6, 6].forEach(x => {
      const e = new THREE.Mesh(eye, eyem); e.position.set(x, 66, 14); g.add(e)
    })
  } else if (kind === 'stand') {
    add(new THREE.BoxGeometry(80, 8, 60), 0, 4, 0)
    add(new THREE.BoxGeometry(80, 45, 8), 0, 22, -26)
    add(new THREE.BoxGeometry(80, 10, 8), 0, 38, -26)
  } else if (kind === 'spinner') {
    add(new THREE.CylinderGeometry(40, 40, 6, 72), 0, 3, 0)
    add(new THREE.TorusGeometry(34, 4, 16, 64), 0, 3, 0)
    add(new THREE.CylinderGeometry(10, 10, 8, 48), 0, 4, 0)
    add(new THREE.CylinderGeometry(5, 5, 12, 32), 0, 6, 0)
  } else if (kind === 'penholder') {
    const shape = new THREE.Shape()
    const R = 35, N = 6
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2
      const x = R * Math.cos(a), z = R * Math.sin(a)
      i === 0 ? shape.moveTo(x, z) : shape.lineTo(x, z)
    }
    shape.closePath()
    const hole = new THREE.Path()
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2
      const x = 31 * Math.cos(a), z = 31 * Math.sin(a)
      i === 0 ? hole.moveTo(x, z) : hole.lineTo(x, z)
    }
    shape.holes.push(hole)
    add(new THREE.ExtrudeGeometry(shape, { depth: 90, bevelEnabled: false }))
  } else {
    add(new THREE.BoxGeometry(80, 60, 70), 0, 30, 0)
  }
  return g
}

function initScene() {
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xf7f5f0)
  camera = new THREE.PerspectiveCamera(45, 1, 1, 5000)
  camera.position.set(220, 220, 300)
  renderer = new THREE.WebGLRenderer({ antialias: true })
  container.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.target.set(0, 80, 0)

  // 灯光
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd8d2c4, 1.1))
  const dir = new THREE.DirectionalLight(0xffffff, 1.4)
  dir.position.set(150, 300, 120)
  scene.add(dir)

  // 打印平台（X1C 256³ 可视）
  buildBox = new THREE.Mesh(
    new THREE.BoxGeometry(BUILD, BUILD, BUILD),
    new THREE.MeshBasicMaterial({ color: 0x2b6cb0, transparent: true, opacity: 0.05, side: THREE.DoubleSide })
  )
  buildBox.position.set(0, BUILD / 2, 0)
  scene.add(buildBox)
  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(BUILD, BUILD, BUILD)),
    new THREE.LineBasicMaterial({ color: 0x9fb4b8, transparent: true, opacity: 0.5 })
  )
  edges.position.set(0, BUILD / 2, 0)
  scene.add(edges)
  const grid = new THREE.GridHelper(BUILD, 8, 0xc9c2b2, 0xe0dbd0)
  scene.add(grid)

  // 模型
  modelGroup = new THREE.Group()
  scene.add(modelGroup)
  loadModel()

  const resize = () => {
    const w = container.value.clientWidth, h = container.value.clientHeight
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
  }
  resize()
  window.addEventListener('resize', resize)
  animate()
}

function animate() {
  frameId = requestAnimationFrame(animate)
  controls.update()
  renderer.render(scene, camera)
}

async function loadModel() {
  loading.value = true
  const d = await api.get(`/orders/${orderId}`)
  order.value = d.order
  if (order.value.model_id && d.order.model_name) {
    // 内置模型：按 kind 程序化重建（order 里无 kind 字段——从 model_name 或 select-model 参数推断）
    // 简化：从后端预设文件路径推断（preset:xxx）
    const mv = await api.get(`/orders/${orderId}`)
    const kind = mv.order.model_name?.replace('内置模型 · ', '') || 'generic'
    modelGroup.add(buildPreset(kind))
    snapToBed()
  } else if (order.value.model_id) {
    // 上传模型：STL 文件从后端获取（demo：内置模型走程序化，上传模型走文件）—— 占位
    ElMessage.warning('上传模型的三维预览需要模型文件服务，demo 用内置模型演示')
  }
  loading.value = false
  updateInfo()
}

// —— 摆放操作 ——
const info = reactive({ bbox: null, rotation: [0, 0, 0], scale: 1, count: 1 })

function meshBBox() {
  const box = new THREE.Box3().setFromObject(modelGroup)
  const size = box.getSize(new THREE.Vector3())
  return [round1(size.x), round1(size.y), round1(size.z)]
}
const round1 = (v) => Math.round(v * 10) / 10

function rotate(axis, deg) {
  modelGroup.rotation[axis] += THREE.MathUtils.degToRad(deg)
  updateInfo()
}
function translate(axis, step) {
  modelGroup.position[axis] += step
  updateInfo()
}
function scaleBy(f) {
  const s = THREE.MathUtils.clamp(modelGroup.scale.x * f, 0.2, 5)
  modelGroup.scale.setScalar(s)
  updateInfo()
}
function snapToBed() {
  const box = new THREE.Box3().setFromObject(modelGroup)
  const minY = box.min.y
  modelGroup.position.y -= minY
  updateInfo()
}
function autoArrange() {
  const box = new THREE.Box3().setFromObject(modelGroup)
  const size = box.getSize(new THREE.Vector3())
  modelGroup.position.x = -(size.x / 2)
  modelGroup.position.z = -(size.z / 2)
  snapToBed()
  updateInfo()
}
function arrayCopy(n) {
  // 简单阵列：按 nx × nz 复制模型（demo 用 clone 原始网格）
  const src = modelGroup.children.filter(c => c.isMesh)
  const positions = []
  const box = new THREE.Box3().setFromObject(modelGroup)
  const size = box.getSize(new THREE.Vector3())
  for (let i = 0; i < n; i++)
    for (let j = 0; j < n; j++)
      positions.push([i * (size.x + 6), 0, j * (size.z + 6)])
  modelGroup.children = []
  positions.forEach(([x, y, z]) => {
    src.forEach(m => {
      const c = m.clone()
      c.position.set(x, y, z)
      modelGroup.add(c)
    })
  })
  info.count = n * n
  updateInfo()
}
function resetPose() {
  modelGroup.rotation.set(0, 0, 0)
  modelGroup.scale.setScalar(1)
  modelGroup.position.set(0, 0, 0)
  loadModel()
}
function updateInfo() {
  const box = new THREE.Box3().setFromObject(modelGroup)
  const size = box.getSize(new THREE.Vector3())
  info.bbox = [round1(size.x), round1(size.y), round1(size.z)]
  info.rotation = modelGroup.rotation.toArray().map(r => Math.round(THREE.MathUtils.radToDeg(r)))
  info.scale = round1(modelGroup.scale.x)
}

// —— 参数选择 ——
const form = reactive({ material: 'pla', color: '#E8602C', preset: 'standard', selfFilament: false })
const advanced = ref(false)
const advancedParams = reactive({ layerHeight: 0.2, infill: 20, supports: 'auto' })

// Val1 结果弹窗
const val1Visible = ref(false)
const val1 = ref(null)
const appealNote = ref('')

async function submit() {
  if (!info.bbox) return ElMessage.warning('请先完成摆放')
  if (info.bbox.some((v, i) => v > [BUILD, BUILD, BUILD][i])) return ElMessage.error('模型超出打印平台范围，请缩放')
  submitting.value = true
  const params = advanced.value
    ? { preset: null, layer_height: advancedParams.layerHeight, infill: advancedParams.infill, supports: advancedParams.supports }
    : { preset: form.preset }
  try {
    const d = await api.post(`/orders/${orderId}/placement`, {
      placement: { rotation: info.rotation, scale: info.scale, position: modelGroup.position.toArray() },
      geometry: { bbox: info.bbox },
      material_id: form.material,
      color: form.color,
      params,
      self_filament: form.selfFilament,
    })
    order.value = d.order
    val1.value = d.val1
    val1Visible.value = true
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

async function appeal() {
  await api.post(`/orders/${orderId}/appeal`, { note: appealNote.value })
  ElMessage.success('已提交申诉，等待负责人人工审核')
  val1Visible.value = false
  router.push(`/orders/${orderId}`)
}
async function resubmit() {
  val1Visible.value = false
  router.push(`/create/${orderId}`)
}
function goDetail() {
  val1Visible.value = false
  router.push(`/orders/${orderId}`)
}

watch(() => form.material, () => {
  const m = app.meta?.materials?.find(x => x.id === form.material)
  if (m?.colors?.length) form.color = m.colors[0]
}, { immediate: true })

onMounted(initScene)
onBeforeUnmount(() => {
  cancelAnimationFrame(frameId)
  window.removeEventListener('resize', null)
  renderer?.dispose()
})
</script>

<template>
  <div style="height: calc(100vh - 58px); display: flex">
    <!-- 3D 视口 -->
    <div ref="container" style="flex: 1; position: relative; background: var(--paper)">
      <div style="position: absolute; top: 12px; left: 14px; z-index: 5; background: rgba(255,255,255,.85);
                  border-radius: 8px; padding: 8px 12px; font-size: 12.5px; box-shadow: var(--shadow)">
        打印平台 <b>256×256×256mm</b> · 拖拽旋转视角 · 右键平移 · 滚轮缩放
      </div>
      <div v-loading="loading" style="position: absolute; inset: 0; z-index: 4" />
    </div>

    <!-- 右侧面板 -->
    <div style="width: 330px; border-left: 1px solid var(--line); background: var(--card); overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 16px">
      <div>
        <div style="font-weight: 700">需求 O{{ orderId }}</div>
        <div class="mono muted" style="font-size: 12px">尺寸：{{ info.bbox ? `${info.bbox[0]} × ${info.bbox[1]} × ${info.bbox[2]} mm` : '—' }}</div>
        <div class="mono muted" style="font-size: 12px">角度：{{ info.rotation.join('° ') }}° · 缩放 ×{{ info.scale }} · {{ info.count }} 个</div>
      </div>

      <!-- 摆放操作 -->
      <el-collapse v-model="activeOps">
        <el-collapse-item title="摆放操作（§4.3）" name="ops">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px">
            <el-button size="small" @click="rotate('x', 15)">绕X转 15°</el-button>
            <el-button size="small" @click="rotate('y', 15)">绕Y转 15°</el-button>
            <el-button size="small" @click="rotate('z', 15)">绕Z转 15°</el-button>
            <el-button size="small" @click="snapToBed">吸底</el-button>
            <el-button size="small" @click="autoArrange">自动摆放</el-button>
            <el-button size="small" @click="resetPose">重置</el-button>
            <el-button size="small" @click="scaleBy(1.1)">放大 10%</el-button>
            <el-button size="small" @click="scaleBy(1 / 1.1)">缩小 10%</el-button>
            <el-button size="small" @click="translate('y', 5)">上移 5mm</el-button>
            <el-button size="small" @click="translate('y', -5)">下移 5mm</el-button>
            <el-button size="small" @click="arrayCopy(2)">阵列 2×2</el-button>
            <el-button size="small" @click="arrayCopy(3)">阵列 3×3</el-button>
          </div>
          <div class="muted" style="font-size: 12px; margin-top: 6px">摆放定好的方向/尺寸/矩阵将作为约束传给切片器，不被擅自覆盖（§4.4）</div>
        </el-collapse-item>
      </el-collapse>

      <!-- 耗材与参数 -->
      <div>
        <div style="font-weight: 700; margin-bottom: 8px">耗材与参数</div>
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
          <el-form-item label="参数">
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
              <div style="display: flex; gap: 8px; width: 100%; flex-wrap: wrap">
                <el-input-number v-model="advancedParams.layerHeight" :step="0.04" :min="0.08" :max="0.32" size="small" />
                <el-input-number v-model="advancedParams.infill" :step="5" :min="0" :max="100" size="small" />
                <el-select v-model="advancedParams.supports" size="small">
                  <el-option value="auto" label="自动支撑" />
                  <el-option value="none" label="无支撑" />
                </el-select>
              </div>
              <div style="width: 100%">
                <el-link type="primary" @click="advanced = false">← 回到标准档</el-link>
              </div>
            </template>
          </el-form-item>
          <el-form-item>
            <el-switch v-model="form.selfFilament" active-text="自备耗材（§16.3）" />
          </el-form-item>
        </el-form>
      </div>

      <el-button type="primary" size="large" :loading="submitting" @click="submit">提交 Val1 审核</el-button>
      <el-button @click="router.push(`/orders/${orderId}`)">返回订单</el-button>
    </div>

    <!-- Val1 结果 -->
    <el-dialog v-model="val1Visible" width="560px" :close-on-click-modal="false">
      <template #header><b>Val1 模型审核结果（§5）</b></template>
      <div v-if="val1" style="display: flex; flex-direction: column; gap: 10px">
        <el-alert :type="val1.result === '通过' ? 'success' : val1.result === '警告' ? 'warning' : 'error'"
                  :title="`审核结果：${val1.result}`" :description="val1.summary" show-icon :closable="false" />
        <el-table :data="val1.items" size="small">
          <el-table-column prop="name" label="检查项" />
          <el-table-column label="结果" width="90">
            <template #default="{ row }">
              <span class="tag" :class="row.level === 'pass' ? 'tag-pass' : row.level === 'warn' ? 'tag-warn' : 'tag-fail'">
                {{ row.level === 'pass' ? '通过' : row.level === 'warn' ? '警告' : '不通过' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="说明" />
        </el-table>

        <div v-if="val1.result === '通过'">
          <el-alert type="success" :closable="false" title="模型满足制造条件，已进入切片与 Val2 审核"
                    description="切片由服务端完成（预计时间/重量以切片器输出为准），负责人审核通过后即可打印" />
          <el-button type="primary" style="margin-top: 10px; width: 100%" @click="goDetail">查看订单追踪</el-button>
        </div>
        <div v-else-if="val1.result === '警告'">
          <el-input v-model="appealNote" type="textarea" :rows="2" placeholder="申诉说明：说明为什么接受风险…" />
          <div style="display: flex; gap: 8px; margin-top: 8px">
            <el-button type="warning" style="flex: 1" @click="appeal">接受风险并申诉（§5.3）</el-button>
            <el-button style="flex: 1" @click="resubmit">修改模型重新提交</el-button>
          </div>
        </div>
        <div v-else>
          <el-alert type="error" :closable="false" title="当前条件下无法打印"
                    description="根据检查结果修改模型后重新提交，或让 AI 重新生成（§5.4）" />
          <el-button style="width: 100%; margin-top: 8px" @click="resubmit">返回修改模型</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>
