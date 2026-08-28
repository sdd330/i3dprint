<script setup>
// 模型摆放工作区（类 BambuStudio，§4.3）—— Three.js 本地渲染，不依赖 CDN
// 摆放约束（旋转/平移/缩放/阵列/吸底/自动摆放）作为 geometry.bbox 提交，Val1 以服务端 trimesh 为准
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { buildPreset, loadModelIntoGroup } from '@/three/models'
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

// 内置模型构建已提取到 @/three/models（buildPreset）

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
  try {
    const d = await api.get(`/orders/${orderId}`)
    order.value = d.order
    if (order.value.model_id) await loadModelIntoGroup(d.order, modelGroup)
    snapToBed()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
    updateInfo()
  }
}

// —— 摆放操作 ——
const info = reactive({ bbox: null, rotation: [0, 0, 0], scale: 1, scaleText: '1 / 1 / 1', count: 1 })

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

// 指定某轴缩放到 xx mm（可选等比例，类 Blender 精确缩放）
const dimTarget = reactive({ axis: 'y', size: 100, uniform: true })
function scaleToSize() {
  const cur = meshBBox()
  if (!cur || !cur[0]) return ElMessage.warning('请先加载模型')
  const idx = { x: 0, y: 1, z: 2 }[dimTarget.axis]
  const curLen = cur[idx]
  if (curLen <= 0 || !isFinite(curLen)) return ElMessage.warning('无法读取当前轴长度')
  if (dimTarget.size <= 0) return ElMessage.warning('请输入有效的目标尺寸')
  const factor = dimTarget.size / curLen
  if (dimTarget.uniform) {
    // 等比例：整体缩放，目标轴变为 xx mm，其余轴同比例
    modelGroup.scale.multiplyScalar(factor)
  } else {
    // 非等比：仅该轴缩放（模型拉伸）
    modelGroup.scale[dimTarget.axis] *= factor
  }
  updateInfo()
  ElMessage.success(`已${dimTarget.uniform ? '等比' : '沿' + dimTarget.axis.toUpperCase() + '轴'}缩放到 ${dimTarget.size}mm（当前 ${meshBBox().join(' × ')}mm）`)
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
  info.rotation = modelGroup.rotation.toArray().slice(0, 3).map(r => Math.round(THREE.MathUtils.radToDeg(r)))
  const { x, y, z } = modelGroup.scale
  info.scale = round1(x)
  info.scaleText = `${round1(x)} / ${round1(y)} / ${round1(z)}`
}

// Val1 结果弹窗（§5：摆放后独立审核，不涉及耗材/参数）
const val1Visible = ref(false)
const val1 = ref(null)
const appealNote = ref('')

async function submit() {
  if (!info.bbox) return ElMessage.warning('请先完成摆放')
  if (info.bbox.some((v, i) => v > [BUILD, BUILD, BUILD][i])) return ElMessage.error('模型超出打印平台范围，请缩放')
  submitting.value = true
  try {
    const d = await api.post(`/orders/${orderId}/placement`, {
      placement: { rotation: info.rotation, scale: info.scale, position: modelGroup.position.toArray() },
      geometry: { bbox: info.bbox },
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
function goParams() {
  val1Visible.value = false
  router.push(`/create/${orderId}/params`)
}
function backToSelect() {
  val1Visible.value = false
  router.push(`/create?id=${orderId}`)
}

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
        <div class="mono muted" style="font-size: 12px">角度：{{ info.rotation.join('° ') }}° · 缩放 ×{{ info.scaleText }} · {{ info.count }} 个</div>
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
          </div>
          <div style="display: flex; gap: 6px; margin-top: 8px; align-items: center">
            <el-select v-model="dimTarget.axis" size="small" style="width: 66px">
              <el-option v-for="a in ['x', 'y', 'z']" :key="a" :value="a" :label="a.toUpperCase()" />
            </el-select>
            <el-input-number v-model="dimTarget.size" size="small" :min="1" :max="256" :step="10" style="width: 100px" />
            <el-checkbox v-model="dimTarget.uniform" size="small">等比例</el-checkbox>
            <el-button size="small" type="primary" @click="scaleToSize">缩放到 mm</el-button>
          </div>
          <div class="muted" style="font-size: 12px; margin-top: 4px">类 Blender 精确缩放：把 {{ dimTarget.axis.toUpperCase() }} 轴缩放到指定毫米；勾选等比例则整体等比缩放</div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px">
            <el-button size="small" @click="translate('y', 5)">上移 5mm</el-button>
            <el-button size="small" @click="translate('y', -5)">下移 5mm</el-button>
            <el-button size="small" @click="arrayCopy(2)">阵列 2×2</el-button>
            <el-button size="small" @click="arrayCopy(3)">阵列 3×3</el-button>
          </div>
          <div class="muted" style="font-size: 12px; margin-top: 6px">摆放定好的方向/尺寸/矩阵将作为约束传给切片器，不被擅自覆盖（§4.4）</div>
        </el-collapse-item>
      </el-collapse>

      <el-button type="primary" size="large" :loading="submitting" @click="submit">提交 Val1 审核</el-button>
      <el-button @click="router.push(`/orders/${orderId}`)">返回订单</el-button>
    </div>


    <!-- Val1 审核结果（§5） -->
    <el-dialog v-model="val1Visible" width="580px" :close-on-click-modal="false">
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
          <el-alert type="success" :closable="false" title="模型满足制造条件"
                    description="接下来选择耗材与打印参数，然后云端切片（§4.1）" />
          <el-button type="primary" style="margin-top: 10px; width: 100%" @click="goParams">去选择耗材与参数 →</el-button>
        </div>
        <div v-else-if="val1.result === '警告'">
          <el-input v-model="appealNote" type="textarea" :rows="2" placeholder="申诉说明：说明为什么接受风险…" />
          <div style="display: flex; gap: 8px; margin-top: 8px">
            <el-button type="warning" style="flex: 1" @click="appeal">接受风险并申诉（§5.3）</el-button>
            <el-button style="flex: 1" @click="backToSelect">修改模型重新提交</el-button>
          </div>
        </div>
        <div v-else>
          <el-alert type="error" :closable="false" title="当前条件下无法打印"
                    description="根据检查结果修改模型后重新提交（§5.4）" />
          <el-button style="width: 100%; margin-top: 8px" @click="backToSelect">返回修改模型</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>
