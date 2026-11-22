<script setup lang="ts">
import type { OrderDetail } from '#shared/print'
import { safeColor } from '#shared/print'

const route = useRoute()
const code = computed(() => String(route.params.code))
const materialNo = ref('pla')
const color = ref('#d946ef')
const strength = ref('标准')
const note = ref('')
const pending = ref(false)
const message = ref('')
const { data, error } = await useAsyncData(
  () => `print-req-${code.value}`,
  () => $fetch<OrderDetail>(`/api/orders/${code.value}`),
)

watch(data, (order) => {
  if (!order) return
  materialNo.value = order.materialNo || 'pla'
  color.value = safeColor(order.color)
}, { immediate: true })

async function submit() {
  message.value = ''
  pending.value = true
  try {
    await $fetch(`/api/orders/${code.value}/print`, {
      method: 'POST',
      body: { materialNo: materialNo.value, color: color.value, strength: strength.value, note: note.value },
    })
    await navigateTo(`/orders/${code.value}`)
  } catch {
    message.value = '保存失败'
    pending.value = false
  }
}

useSeoMeta({ title: '打印需求 · Violet Z' })
</script>

<template>
  <div class="max-w-xl">
    <p v-if="error" class="text-glow" role="alert">没有这条记录</p>
    <form v-else class="grid gap-4" @submit.prevent="submit">
      <h1 class="text-3xl">{{ data?.name }}</h1>
      <p class="text-mute">材料、强度和给执行人的备注会写进打印清单。耗时与克重按几何估算，不冒充切片结果。</p>
      <label class="grid gap-2">
        <span class="text-sm text-mute">材料</span>
        <input v-model="materialNo" class="rounded-xl border border-line bg-panel px-3 py-2" maxlength="32" />
      </label>
      <label class="grid gap-2">
        <span class="text-sm text-mute">颜色</span>
        <input v-model="color" class="h-10 w-24 rounded-xl border border-line bg-panel" type="color" />
      </label>
      <label class="grid gap-2">
        <span class="text-sm text-mute">强度</span>
        <select v-model="strength" class="rounded-xl border border-line bg-panel px-3 py-2">
          <option>轻量</option>
          <option>标准</option>
          <option>坚固</option>
          <option>超坚固</option>
        </select>
      </label>
      <label class="grid gap-2">
        <span class="text-sm text-mute">给执行人</span>
        <textarea v-model="note" class="min-h-28 rounded-xl border border-line bg-panel px-3 py-2" maxlength="300" />
      </label>
      <p v-if="message" class="text-glow" role="alert">{{ message }}</p>
      <button class="btn-primary w-fit" type="submit" :disabled="pending">写入清单</button>
    </form>
  </div>
</template>
