import { defineStore } from 'pinia'
import { api } from '@/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    token: localStorage.getItem('token') || '',
  }),
  getters: {
    // 负责人侧：root（受保护超级管理员）与 admin（日常负责人）都算
    isAdmin: (s) => ['root', 'admin'].includes(s.user?.role),
    isRoot: (s) => s.user?.role === 'root',
    isLoggedIn: (s) => !!s.token,
    hasPerm: (s) => (p) => (s.user?.permissions || []).includes(p),
  },
  actions: {
    async login(username, password) {
      const d = await api.post('/auth/login', { username, password })
      this._set(d)
    },
    async register(body) {
      const d = await api.post('/auth/register', body)
      this._set(d)
    },
    _set(d) {
      this.token = d.token
      this.user = d.user
      localStorage.setItem('token', d.token)
      localStorage.setItem('user', JSON.stringify(d.user))
    },
    logout() {
      this.user = null
      this.token = ''
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})

export const useAppStore = defineStore('app', {
  state: () => ({ meta: null }),
  getters: {
    // 能力开关（后端 /meta/bootstrap → flow）：未加载时按「关闭」处理，避免先闪出入口
    flow: (s) => s.meta?.flow || {},
    // 收费/费用信息暂时隐去（用户要求）：false 时全部费用相关 UI 都不渲染
    billingVisible: (s) => !!s.meta?.flow?.billing_visible,
    materials: (s) => s.meta?.materials || [],
    strengthTiers: (s) => s.meta?.strength_tiers || [],
  },
  actions: {
    async loadMeta() {
      this.meta = await api.get('/meta/bootstrap')
    },
  },
})
