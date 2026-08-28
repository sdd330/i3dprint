import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores'

const routes = [
  { path: '/', component: () => import('@/views/Home.vue'), meta: { public: true } },
  { path: '/login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  { path: '/orders', component: () => import('@/views/OrderList.vue') },
  { path: '/orders/:id', component: () => import('@/views/OrderDetail.vue') },
  { path: '/create', component: () => import('@/views/CreateOrder.vue') },
  { path: '/create/:id/workspace', component: () => import('@/views/Workspace.vue') },
  { path: '/create/:id/params', component: () => import('@/views/ParamsConfig.vue') },
  { path: '/ai', component: () => import('@/views/AiModeling.vue') },
  { path: '/manual', component: () => import('@/views/Manual.vue'), meta: { public: true } },
  // 负责人端
  { path: '/admin', component: () => import('@/views/admin/AdminHome.vue'), meta: { admin: true } },
  { path: '/admin/config', component: () => import('@/views/admin/ConfigCenter.vue'), meta: { admin: true } },
  { path: '/admin/roles', component: () => import('@/views/admin/RoleManage.vue'), meta: { admin: true } },
  { path: '/admin/qa-config', component: () => import('@/views/admin/QaConfig.vue'), meta: { admin: true } },
  { path: '/admin/audits', component: () => import('@/views/admin/AuditLogs.vue'), meta: { admin: true } },
  { path: '/admin/settings', component: () => import('@/views/admin/Settings.vue'), meta: { admin: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.admin && !auth.isAdmin) return { path: '/', query: { needAdmin: '1' } }
  if (!to.meta.public && !auth.isLoggedIn) return { path: '/login', query: { redirect: to.fullPath } }
  return true
})

export default router
