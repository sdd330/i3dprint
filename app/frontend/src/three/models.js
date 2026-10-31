// 共享 3D 模型构建/加载（摆放工作区 与 参数配置页 复用）
import * as THREE from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'

export const DEFAULT_MAT = () => new THREE.MeshStandardMaterial({ color: 0x7A4BB5, roughness: 0.55, metalness: 0.05 })

// 内置演示模型（与后端 trimesh build_preset 对应）
export function buildPreset(kind) {
  const g = new THREE.Group()
  const mat = DEFAULT_MAT
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

export function isPresetModel(order) {
  return order?.model_name?.includes('内置模型')
}

// 按订单加载模型到 group（内置 → 程序化；上传 → 后端文件真实预览）
export async function loadModelIntoGroup(order, group, { mat = DEFAULT_MAT } = {}) {
  if (isPresetModel(order)) {
    const kind = order.model_name.replace('内置模型 · ', '') || 'generic'
    group.add(buildPreset(kind))
    return
  }
  const res = await fetch(`/api/models/${order.model_version_id}/file`, {
    headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
  })
  if (!res.ok) throw new Error('模型预览加载失败，请重试')
  const ctype = res.headers.get('content-type') || ''
  const buf = await res.arrayBuffer()
  if (ctype.includes('obj')) {
    const g = new OBJLoader().parse(new TextDecoder().decode(buf))
    g.traverse((child) => { if (child.isMesh) child.material = mat() })
    group.add(g)
  } else {
    const geo = new STLLoader().parse(buf)
    group.add(new THREE.Mesh(geo, mat()))
  }
}

// 应用摆放（旋转/缩放/平移）到 group；返回摆放后 bbox [x,y,z]
export function applyPlacement(group, placement) {
  if (!placement) return
  const [rx, ry, rz] = placement.rotation || [0, 0, 0]
  group.rotation.set(THREE.MathUtils.degToRad(rx), THREE.MathUtils.degToRad(ry), THREE.MathUtils.degToRad(rz))
  if (placement.scale) group.scale.setScalar(placement.scale)
  if (placement.position) group.position.fromArray(placement.position)
}

export function groupBBox(group) {
  const box = new THREE.Box3().setFromObject(group)
  if (box.isEmpty()) return null
  const size = box.getSize(new THREE.Vector3())
  return [Math.round(size.x * 10) / 10, Math.round(size.y * 10) / 10, Math.round(size.z * 10) / 10]
}
