<script setup>
// 模型摆放工作区（类 BambuStudio，§4.3）—— Three.js 本地渲染，不依赖 CDN
// 摆放约束（旋转/平移/缩放/阵列/吸底/自动摆放）作为 geometry.bbox 提交，Val1 以服务端 trimesh 为准
//
// 2026-10 交互改进（Val1 前的缩放界面）：
//   · 直接拖模型：在平台上按住模型就能拖动（XZ 平面移动 + 1mm 吸附），不必去找箭头手柄
//   · 三轴手柄：移动 / 旋转 / 缩放 切换（快捷键 G / R / S），旋转 15° 吸附、缩放 0.05 吸附
//   · 滑块缩放 + 按毫米精确缩放（等比 / 单轴），缩放在三轴上都可读可改
//   · 一键聚焦（F）、吸底锁定、自动摆放、越界即时提示
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js'
import { loadModelIntoGroup } from '@/three/models'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()
const orderId = Number(route.params.id)
const order = ref(null)
const container = ref(null)
const loading = ref(true)
const submitting = ref(false)

// —— Three.js 场景 ——
let scene, camera, renderer, controls, transform, transformHelper, modelGroup, frameId
const BUILD = 256
const raycaster = new THREE.Raycaster()
const pointerNdc = new THREE.Vector2()
const dragPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)
let baseMeshes = []          // 阵列基准（模型加载后的原始网格副本）
let draggingModel = false
const dragOffset = new THREE.Vector3()

function initScene() {
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xf7f5f0)
  camera = new THREE.PerspectiveCamera(45, 1, 1, 5000)
  camera.position.set(220, 220, 300)
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.domElement.style.touchAction = 'none'
  container.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.target.set(0, 40, 0)
  controls.maxDistance = 1200

  // 灯光
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd8d2c4, 1.1))
  const dir = new THREE.DirectionalLight(0xffffff, 1.4)
  dir.position.set(150, 300, 120)
  scene.add(dir)

  // 打印平台（X1C 256³ 可视）
  const box = new THREE.Mesh(
    new THREE.BoxGeometry(BUILD, BUILD, BUILD),
    new THREE.MeshBasicMaterial({ color: 0x2b6cb0, transparent: true, opacity: 0.05, side: THREE.DoubleSide })
  )
  box.position.set(0, BUILD / 2, 0)
  scene.add(box)
  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(BUILD, BUILD, BUILD)),
    new THREE.LineBasicMaterial({ color: 0x9fb4b8, transparent: true, opacity: 0.5 })
  )
  edges.position.set(0, BUILD / 2, 0)
  scene.add(edges)
  scene.add(new THREE.GridHelper(BUILD, 16, 0xc9c2b2, 0xe0dbd0))

  // 模型
  modelGroup = new THREE.Group()
  scene.add(modelGroup)

  // 三轴手柄（移动 / 旋转 / 缩放）
  transform = new TransformControls(camera, renderer.domElement)
  transform.setSize(0.85)
  transform.setTranslationSnap(1)                        // 平移吸附 1mm
  transform.setRotationSnap(THREE.MathUtils.degToRad(15)) // 旋转吸附 15°
  transform.setScaleSnap(0.05)                           // 缩放吸附 0.05
  transform.attach(modelGroup)
  transformHelper = transform.getHelper()
  scene.add(transformHelper)
  transform.addEventListener('dragging-changed', (e) => {
    controls.enabled = !e.value          // 拖手柄时禁用视角旋转
    if (!e.value) afterTransform()
  })
  transform.addEventListener('objectChange', () => {
    if (bedLock.value && mode.value === 'translate') sitOnBed()
    updateInfo()
  })

  // 模型指针交互：拖模型本体移动 / 点击选中
  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('keydown', onKeyDown)

  loadModel()

  const resize = () => {
    if (!container.value) return
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

async function loadModel({ restore = true } = {}) {
  loading.value = true
  try {
    const d = await api.get(`/orders/${orderId}`)
    order.value = d.order
    clearModel()
    if (order.value.model_id) {
      await loadModelIntoGroup(d.order, modelGroup)
      // 旧摆放（返回修改时）恢复，否则吸底 + 聚焦
      const p = restore ? order.value.placement : null
      if (p && (p.rotation || p.scale || p.position)) applySavedPlacement(p)
      else sitOnBed()
      baseMeshes = modelGroup.children.map(c => c.clone(true))
      fitView()
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
    updateInfo()
  }
}

function clearModel() {
  // 注意：不 dispose 几何——阵列基准 baseMeshes 与实例共享 geometry，dispose 会让副本变空
  for (const c of [...modelGroup.children]) modelGroup.remove(c)
  modelGroup.position.set(0, 0, 0)
  modelGroup.rotation.set(0, 0, 0)
  modelGroup.scale.setScalar(1)
}

function applySavedPlacement(p) {
  const [rx, ry, rz] = p.rotation || [0, 0, 0]
  modelGroup.rotation.set(THREE.MathUtils.degToRad(rx), THREE.MathUtils.degToRad(ry), THREE.MathUtils.degToRad(rz))
  const sc = p.scale
  if (Array.isArray(sc)) modelGroup.scale.set(sc[0] || 1, sc[1] || 1, sc[2] || 1)
  else if (sc) modelGroup.scale.setScalar(sc)
  if (p.position) modelGroup.position.fromArray(p.position)
}

// —— 相机聚焦 ——
function fitView() {
  const b = new THREE.Box3().setFromObject(modelGroup)
  if (b.isEmpty()) return
  const size = b.getSize(new THREE.Vector3())
  const center = b.getCenter(new THREE.Vector3())
  const maxDim = Math.max(size.x, size.y, size.z) || 60
  const dist = maxDim * 1.9 + 60
  const dirV = new THREE.Vector3(0.62, 0.72, 1).normalize()
  camera.position.copy(center.clone().add(dirV.multiplyScalar(dist)))
  camera.near = Math.max(1, dist / 200)
  camera.far = dist * 20
  camera.updateProjectionMatrix()
  controls.target.copy(center)
  controls.update()
}

// —— 摆放操作 ——
const mode = ref('translate')   // translate | rotate | scale
const bedLock = ref(true)       // 吸底锁定：拖动时只允许 XZ 移动并贴平台
const info = reactive({ bbox: null, rotation: [0, 0, 0], scaleText: '1 / 1 / 1', count: 1, oversize: false })

function setMode(m) {
  mode.value = m
  transform.setMode(m)
  transform.showY = !(m === 'translate' && bedLock.value)  // 吸底锁定时不提供 Y 轴拖动
  updateInfo()
}
function toggleBedLock() {
  bedLock.value = !bedLock.value
  if (bedLock.value) sitOnBed()
  setMode(mode.value)
}

function snapToBed() {
  sitOnBed()
  updateInfo()
}

function rotate(axis, deg) {
  modelGroup.rotation[axis] += THREE.MathUtils.degToRad(deg)
  if (bedLock.value) sitOnBed()
  updateInfo()
}

const round1 = (v) => Math.round(v * 10) / 10
function meshBBox() {
  const b = new THREE.Box3().setFromObject(modelGroup)
  const size = b.getSize(new THREE.Vector3())
  return [round1(size.x), round1(size.y), round1(size.z)]
}

// 吸底：让模型最低点贴平台（y=0）
function sitOnBed() {
  const b = new THREE.Box3().setFromObject(modelGroup)
  modelGroup.position.y -= b.min.y
}
// 限位：把模型推回平台范围内（X/Z 各 ±128）
function clampToBed() {
  const b = new THREE.Box3().setFromObject(modelGroup)
  if (b.isEmpty()) return
  const half = BUILD / 2
  if (b.min.x < -half) modelGroup.position.x += -half - b.min.x
  else if (b.max.x > half) modelGroup.position.x += half - b.max.x
  if (b.min.z < -half) modelGroup.position.z += -half - b.min.z
  else if (b.max.z > half) modelGroup.position.z += half - b.max.z
}
function afterTransform() {
  if (bedLock.value) sitOnBed()
  clampToBed()
  updateInfo()
}

// 滑块缩放（等比）
const scaleSlider = ref(100)  // 百分比
function applySliderScale() {
  const s = scaleSlider.value / 100
  // 以当前 X 轴比例作为基准，保持三轴相对关系
  const cur = modelGroup.scale.x || 1
  modelGroup.scale.multiplyScalar(s / cur)
  if (bedLock.value) sitOnBed()
  updateInfo()
}

// 精确缩放到指定毫米（等比 / 单轴）
const dimTarget = reactive({ axis: 'y', size: 100, uniform: true })
function scaleToSize() {
  const cur = meshBBox()
  if (!cur || !cur[0]) return ElMessage.warning('请先加载模型')
  const idx = { x: 0, y: 1, z: 2 }[dimTarget.axis]
  const curLen = cur[idx]
  if (curLen <= 0 || !isFinite(curLen)) return ElMessage.warning('无法读取当前轴长度')
  if (!dimTarget.size || dimTarget.size <= 0) return ElMessage.warning('请输入有效的目标尺寸')
  const factor = dimTarget.size / curLen
  if (dimTarget.uniform) {
    modelGroup.scale.multiplyScalar(factor)
  } else {
    modelGroup.scale[dimTarget.axis] *= factor
    if (modelGroup.scale[dimTarget.axis] < 0.05) modelGroup.scale[dimTarget.axis] = 0.05
  }
  if (bedLock.value) sitOnBed()
  clampToBed()
  updateInfo()
  ElMessage.success(`已${dimTarget.uniform ? '等比' : '沿 ' + dimTarget.axis.toUpperCase() + ' 轴'}缩放到 ${dimTarget.size}mm（当前 ${meshBBox().join(' × ')}mm）`)
}

function autoArrange() {
  const b = new THREE.Box3().setFromObject(modelGroup)
  const center = b.getCenter(new THREE.Vector3())
  modelGroup.position.x -= center.x          // 居中到平台中心
  modelGroup.position.z -= center.z
  if (bedLock.value) sitOnBed()
  clampToBed()
  updateInfo()
}

function resetPose() {
  modelGroup.rotation.set(0, 0, 0)
  modelGroup.scale.setScalar(1)
  modelGroup.position.set(0, 0, 0)
  scaleSlider.value = 100
  loadModel({ restore: false })
}

// 阵列：以阵列前形态为基准复制 nx × nz（不会累乘）
const gridN = ref(1)
function arrayCopy(n) {
  if (!baseMeshes.length) return ElMessage.warning('请先加载模型')
  gridN.value = n
  const savedRot = modelGroup.rotation.clone()
  const savedScale = modelGroup.scale.clone()
  const savedPos = modelGroup.position.clone()
  modelGroup.rotation.set(0, 0, 0)
  modelGroup.scale.setScalar(1)
  modelGroup.position.set(0, 0, 0)
  for (const c of [...modelGroup.children]) modelGroup.remove(c)
  // 先放一份量测尺寸
  baseMeshes.forEach(m => modelGroup.add(m.clone(true)))
  const b = new THREE.Box3().setFromObject(modelGroup)
  const size = b.getSize(new THREE.Vector3())
  const stepX = size.x + 6, stepZ = size.z + 6
  const offX = -((n - 1) * stepX) / 2, offZ = -((n - 1) * stepZ) / 2
  for (const c of [...modelGroup.children]) modelGroup.remove(c)
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      baseMeshes.forEach(m => {
        const c = m.clone(true)
        c.position.x += offX + i * stepX
        c.position.z += offZ + j * stepZ
        modelGroup.add(c)
      })
    }
  }
  modelGroup.rotation.copy(savedRot)
  modelGroup.scale.copy(savedScale)
  modelGroup.position.copy(savedPos)
  if (bedLock.value) sitOnBed()
  clampToBed()
  updateInfo()
}

function updateInfo() {
  const b = new THREE.Box3().setFromObject(modelGroup)
  if (b.isEmpty()) { info.bbox = null; return }
  const size = b.getSize(new THREE.Vector3())
  info.bbox = [round1(size.x), round1(size.y), round1(size.z)]
  info.oversize = info.bbox.some((v, i) => v > [BUILD, BUILD, BUILD][i] + 0.01)
  info.rotation = modelGroup.rotation.toArray().slice(0, 3).map(r => Math.round(THREE.MathUtils.radToDeg(r)))
  const { x, y, z } = modelGroup.scale
  info.scaleText = `${round1(x)} / ${round1(y)} / ${round1(z)}`
  info.count = gridN.value ** 2
}

// —— 指针交互：直接拖模型（XZ 平面） ——
function setPointerFromEvent(e) {
  const rect = renderer.domElement.getBoundingClientRect()
  pointerNdc.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
  pointerNdc.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointerNdc, camera)
}

function onPointerDown(e) {
  if (e.button !== 0 || transform.axis || transform.dragging) return  // 手柄交互交给 TransformControls
  if (loading.value || !modelGroup) return
  setPointerFromEvent(e)
  const hits = raycaster.intersectObjects(modelGroup.children, true)
  if (!hits.length) return
  draggingModel = true
  controls.enabled = false
  const hitY = hits[0].point.y
  dragPlane.set(new THREE.Vector3(0, 1, 0), -hitY)  // 以抓取点高度为拖动平面
  const hit = new THREE.Vector3()
  raycaster.ray.intersectPlane(dragPlane, hit)
  dragOffset.set(modelGroup.position.x - hit.x, 0, modelGroup.position.z - hit.z)
  renderer.domElement.style.cursor = 'grabbing'
}

function onPointerMove(e) {
  if (!draggingModel) return
  setPointerFromEvent(e)
  const hit = new THREE.Vector3()
  if (!raycaster.ray.intersectPlane(dragPlane, hit)) return
  let nx = hit.x + dragOffset.x
  let nz = hit.z + dragOffset.z
  nx = Math.round(nx)   // 1mm 吸附
  nz = Math.round(nz)
  modelGroup.position.x = nx
  modelGroup.position.z = nz
  updateInfo()
}

function onPointerUp() {
  if (!draggingModel) return
  draggingModel = false
  controls.enabled = true
  renderer.domElement.style.cursor = ''
  afterTransform()
}

function onKeyDown(e) {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return
  const k = e.key.toLowerCase()
  if (k === 'g') setMode('translate')
  else if (k === 'r') setMode('rotate')
  else if (k === 's') setMode('scale')
  else if (k === 'f') fitView()
}

// Val1 结果弹窗（§5：摆放后独立审核，不涉及耗材/参数）
const val1Visible = ref(false)
const val1 = ref(null)
const next = ref('')

async function submit() {
  if (!info.bbox) return ElMessage.warning('请先完成摆放')
  if (info.oversize) return ElMessage.error('模型超出打印平台范围，请缩小后再提交')
  submitting.value = true
  try {
    const sc = modelGroup.scale
    const d = await api.post(`/orders/${orderId}/placement`, {
      placement: {
        rotation: info.rotation,
        scale: [round1(sc.x * 100) / 100, round1(sc.y * 100) / 100, round1(sc.z * 100) / 100],
        position: modelGroup.position.toArray(),
      },
      geometry: { bbox: info.bbox },
    })
    order.value = d.order
    val1.value = d.val1
    next.value = d.next
    val1Visible.value = true
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

function goPrintRequirement() {
  val1Visible.value = false
  router.push(`/create/${orderId}/print-req`)
}
function goOrder() {
  val1Visible.value = false
  router.push(`/orders/${orderId}`)
}
function backToSelect() {
  val1Visible.value = false
  router.push(`/create?id=${orderId}`)
}

const activeOps = ref(['ops'])

onMounted(initScene)
onBeforeUnmount(() => {
  cancelAnimationFrame(frameId)
  window.removeEventListener('resize', null)
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('keydown', onKeyDown)
  transform?.dispose?.()
  controls?.dispose?.()
  renderer?.dispose()
})
</script>

<template>
  <div style="height: calc(100vh - 58px); display: flex">
    <!-- 3D 视口 -->
    <div ref="container" style="flex: 1; position: relative; background: var(--paper)">
      <div style="position: absolute; top: 12px; left: 14px; z-index: 5; background: rgba(255,255,255,.9);
                  border-radius: 8px; padding: 8px 12px; font-size: 12.5px; box-shadow: var(--shadow); line-height: 1.7">
        打印平台 <b>256×256×256mm</b><br />
        <span class="muted">按住模型直接拖动 · 手柄调整 · 空白处拖拽转视角 · 滚轮缩放视角</span><br />
        <span class="muted">快捷键：<b>G</b> 移动 / <b>R</b> 旋转 / <b>S</b> 缩放 / <b>F</b> 聚焦</span>
      </div>

      <!-- 模式切换悬浮条 -->
      <div style="position: absolute; bottom: 16px; left: 50%; transform: translateX(-50%); z-index: 6;
                  background: rgba(255,255,255,.94); border-radius: 12px; padding: 6px; box-shadow: var(--shadow);
                  display: flex; gap: 6px; align-items: center">
        <el-radio-group v-model="mode" size="small" @change="setMode">
          <el-radio-button value="translate">移动 G</el-radio-button>
          <el-radio-button value="rotate">旋转 R</el-radio-button>
          <el-radio-button value="scale">缩放 S</el-radio-button>
        </el-radio-group>
        <el-divider direction="vertical" style="margin: 0 2px" />
        <el-button size="small" :type="bedLock ? 'primary' : ''" @click="toggleBedLock">
          {{ bedLock ? '吸底锁定 ✓' : '吸底锁定' }}
        </el-button>
        <el-button size="small" @click="fitView">聚焦 F</el-button>
      </div>

      <div v-loading="loading" :style="{ position: 'absolute', inset: 0, zIndex: 4, pointerEvents: loading ? 'auto' : 'none' }" />
    </div>

    <!-- 右侧面板 -->
    <div style="width: 332px; border-left: 1px solid var(--line); background: var(--card); overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 14px">
      <div>
        <div style="font-weight: 700">需求 O{{ orderId }}</div>
        <div class="mono" :style="{ fontSize: '12px', color: info.oversize ? 'var(--danger, #c0392b)' : 'var(--ink-soft)' }">
          尺寸：{{ info.bbox ? `${info.bbox[0]} × ${info.bbox[1]} × ${info.bbox[2]} mm` : '—' }}
          {{ info.oversize ? '（超出平台，请缩小）' : '' }}
        </div>
        <div class="mono muted" style="font-size: 12px">角度：{{ info.rotation.join('° ') }}° · 缩放 ×{{ info.scaleText }} · {{ info.count }} 个</div>
      </div>

      <!-- 快速缩放 -->
      <div class="card" style="padding: 12px; margin: 0">
        <div style="font-weight: 600; font-size: 13px; margin-bottom: 6px">快速缩放</div>
        <el-slider v-model="scaleSlider" :min="20" :max="300" :step="5" :format-tooltip="(v) => `${v}%`"
                   @change="applySliderScale" size="small" />
        <div class="muted" style="font-size: 11.5px">滑块以百分比缩放，松手生效；精细调整见下方「按毫米缩放」</div>
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
          </div>

          <div style="display: flex; gap: 6px; margin-top: 10px; align-items: center">
            <el-select v-model="dimTarget.axis" size="small" style="width: 64px">
              <el-option v-for="a in ['x', 'y', 'z']" :key="a" :value="a" :label="a.toUpperCase()" />
            </el-select>
            <el-input-number v-model="dimTarget.size" size="small" :min="1" :max="256" :step="10" style="width: 100px" />
            <el-button size="small" type="primary" @click="scaleToSize">缩放到 mm</el-button>
          </div>
          <el-checkbox v-model="dimTarget.uniform" size="small" style="margin-top: 4px">等比缩放（取消则只拉伸该轴）</el-checkbox>
          <div class="muted" style="font-size: 12px; margin-top: 2px">
            类 Blender 精确缩放：把 {{ dimTarget.axis.toUpperCase() }} 轴缩放到指定毫米
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 10px">
            <el-button size="small" @click="arrayCopy(2)">阵列 2×2</el-button>
            <el-button size="small" @click="arrayCopy(3)">阵列 3×3</el-button>
            <el-button size="small" @click="arrayCopy(1)">取消阵列</el-button>
          </div>
          <div class="muted" style="font-size: 12px; margin-top: 6px">摆放定好的方向/尺寸/矩阵将作为约束交给切片器，不被擅自覆盖（§4.4）</div>
        </el-collapse-item>
      </el-collapse>

      <el-button type="primary" size="large" :loading="submitting" @click="submit">提交 Val1 审核</el-button>
      <el-button @click="router.push(`/orders/${orderId}`)">返回订单</el-button>
    </div>

    <!-- Val1 审核结果（§5） -->
    <el-dialog v-model="val1Visible" width="600px" :close-on-click-modal="false">
      <template #header><b>Val1 模型审核结果（§5）</b></template>
      <div v-if="val1" style="display: flex; flex-direction: column; gap: 10px">
        <el-alert :type="next === 'print_config' ? 'success' : 'warning'"
                  :title="next === 'print_config' ? 'Val1 通过：模型满足制造条件' : `Val1 已标记 ${val1.flagged_items?.length || 0} 项潜在问题`"
                  :description="next === 'print_config'
                    ? '下一步填写打印需求（材料 / 强度 / 进阶参数），生成打印清单'
                    : '系统不会退回你的需求：已转交负责人人工复核，复核结果会显示在订单里'" show-icon :closable="false" />
        <el-table :data="val1.items" size="small" max-height="300">
          <el-table-column prop="name" label="检查项" width="120" />
          <el-table-column label="结果" width="90">
            <template #default="{ row }">
              <span class="tag" :class="row.level === 'pass' ? 'tag-pass' : row.level === 'warn' ? 'tag-warn' : 'tag-fail'">
                {{ row.level === 'pass' ? '通过' : row.level === 'warn' ? '警告' : '不通过' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="说明" />
        </el-table>

        <div v-if="next === 'print_config'">
          <el-button type="primary" style="width: 100%" @click="goPrintRequirement">填写打印需求 →</el-button>
        </div>
        <div v-else>
          <el-alert type="info" :closable="false"
                    title="已标记并转人工复核（无自动退回）"
                    description="负责人会逐项确认这些潜在问题：放行 → 你继续填写打印需求；要求修改 → 你改模型后重新提交；不可打印 → 需求终止。" />
          <el-button style="width: 100%; margin-top: 8px" @click="goOrder">查看订单进度 →</el-button>
          <el-button link style="width: 100%; margin-top: 4px" @click="backToSelect">我想主动改模型</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>
