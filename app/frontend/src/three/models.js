// 共享 3D 模型构建/加载（摆放工作区 与 参数配置页 复用）
import * as THREE from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'

export const DEFAULT_MAT = () => new THREE.MeshStandardMaterial({ color: 0x7A4BB5, roughness: 0.55, metalness: 0.05 })

// 按订单加载模型到 group（生产环境只有"上传的真实文件"这一条路径）
export async function loadModelIntoGroup(order, group, { mat = DEFAULT_MAT } = {}) {
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
