import { defineStore } from 'pinia'
import { api } from '@/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    token: localStorage.getItem('token') || '',
  }),
  getters: {
    isAdmin: (s) => s.user?.role === 'admin',
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
  actions: {
    async loadMeta() {
      this.meta = await api.get('/meta/bootstrap')
    },
  },
})
