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
  // 上传（XHR 以支持进度回调；大文件如 160MB OBJ 实时显示进度）
  upload: (path, file, onProgress) => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', BASE + path)
    const token = localStorage.getItem('token')
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total)
    }
    xhr.onload = () => {
      try {
        const d = JSON.parse(xhr.responseText)
        if (xhr.status >= 200 && xhr.status < 300) resolve(d)
        else reject(new Error(d?.detail || `上传失败 (${xhr.status})`))
      } catch { reject(new Error('上传失败')) }
    }
    xhr.onerror = () => reject(new Error('网络错误，上传中断'))
    const fd = new FormData()
    fd.append('file', file)
    xhr.send(fd)
  }),
}
