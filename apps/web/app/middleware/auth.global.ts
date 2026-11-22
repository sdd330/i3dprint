export default defineNuxtRouteMiddleware(async (to) => {
  if (to.path === '/login' || to.path === '/offline' || to.path.startsWith('/oauth/')) return
  const session = useSessionStore()
  try {
    const me = await $fetch<{ code: string; name: string; role: string }>('/api/me', {
      headers: import.meta.server ? useRequestHeaders(['cookie']) : undefined,
    })
    session.setUser(me)
    if (to.path.startsWith('/admin') && me.role !== 'root' && me.role !== 'admin') {
      return navigateTo('/')
    }
  } catch {
    session.setUser(null)
    return navigateTo({ path: '/login', query: { next: to.fullPath } })
  }
})
