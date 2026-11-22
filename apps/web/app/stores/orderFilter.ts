export const useOrderFilterStore = defineStore('order-filter', () => {
  const status = ref(0)
  const materialNo = ref('')

  function reset() {
    status.value = 0
    materialNo.value = ''
  }

  return { status, materialNo, reset }
})
