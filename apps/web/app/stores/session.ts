export const useSessionStore = defineStore('session', () => {
  const user = ref<{ code: string; name: string; role: string } | null>(null)
  const isStaff = computed(() => user.value?.role === 'root' || user.value?.role === 'admin')

  function setUser(value: { code: string; name: string; role: string } | null) {
    user.value = value
  }

  return { user, isStaff, setUser }
})
