// E3DP API 客户端 —— 统一错误处理 + token 注入

const BASE = '/api'

async function req(method, path, body, opts = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem('token')
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(BASE + path, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined, ...opts,
  })
  let data = null
  try { data = await res.json() } catch { /* 非 JSON */ }
  if (!res.ok) {
    const msg = data?.detail || data?.error || `请求失败 (${res.status})`
    const err = new Error(msg)
    err.status = res.status
    throw err
  }
  return data
}

export const api = {
  get: (p) => req('GET', p),
  post: (p, b) => req('POST', p, b),
  put: (p, b) => req('PUT', p, b),
  del: (p) => req('DELETE', p),
  upload: async (path, file) => {
    const fd = new FormData()
    fd.append('file', file)
    const headers = {}
    const token = localStorage.getItem('token')
    if (token) headers.Authorization = `Bearer ${token}`
    const res = await fetch(BASE + path, { method: 'POST', headers, body: fd })
    const data = await res.json()
    if (!res.ok) throw new Error(data?.detail || '上传失败')
    return data
  },
}
