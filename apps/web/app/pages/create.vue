<script setup lang="ts">
import type { Campaign } from '#shared/print'

const { data: campaigns } = await useAsyncData('open-campaigns', () => $fetch<Campaign[]>('/api/campaigns'))
const openCampaigns = computed(() => (campaigns.value ?? []).filter((item) => item.status === 2))
const form = reactive({
  campaignCode: '',
  name: '',
  materialNo: 'pla',
  color: '#d946ef',
  remark: '',
})
const message = ref('')
const pending = ref(false)

watch(
  openCampaigns,
  (items) => {
    if (!form.campaignCode && items[0]) form.campaignCode = items[0].code
  },
  { immediate: true },
)

async function submit() {
  message.value = ''
  pending.value = true
  try {
    const created = await $fetch<{ code: string }>('/api/orders', { method: 'POST', body: form })
    await navigateTo(`/orders/${created.code}`)
  } catch {
    message.value = '没有创建成功。请确认活动正在开放。'
  } finally {
    pending.value = false
  }
}

useSeoMeta({ title: '创建需求 · Violet Print' })
</script>

<template>
  <div class="max-w-xl">
    <h1 class="text-3xl">创建需求</h1>
    <p class="mt-3 text-mute">选择开放中的活动，写下要打印的东西。在线切片仍关闭，负责人按清单执行。</p>
    <p v-if="openCampaigns.length === 0" class="mt-6 text-mute">当前没有开放中的活动。</p>
    <form v-else class="mt-6 grid gap-4" @submit.prevent="submit">
      <label class="grid gap-2 text-sm text-mute">
        活动
        <select v-model="form.campaignCode" class="h-11 rounded-xl border border-line bg-panel px-3 text-paper" required>
          <option v-for="campaign in openCampaigns" :key="campaign.code" :value="campaign.code">{{ campaign.name }}</option>
        </select>
      </label>
      <label class="grid gap-2 text-sm text-mute">
        名称
        <input v-model="form.name" class="h-11 rounded-xl border border-line bg-panel px-3 text-paper" maxlength="300" required />
      </label>
      <label class="grid gap-2 text-sm text-mute">
        材料
        <select v-model="form.materialNo" class="h-11 rounded-xl border border-line bg-panel px-3 text-paper">
          <option value="pla">PLA</option>
          <option value="petg">PETG</option>
          <option value="abs">ABS</option>
          <option value="tpu">TPU</option>
          <option value="asa">ASA</option>
        </select>
      </label>
      <label class="grid gap-2 text-sm text-mute">
        颜色
        <input v-model="form.color" class="h-11 rounded-xl border border-line bg-panel px-3 text-paper" pattern="#[0-9a-fA-F]{6}" required />
      </label>
      <label class="grid gap-2 text-sm text-mute">
        给执行人的备注
        <textarea v-model="form.remark" class="min-h-24 rounded-xl border border-line bg-panel px-3 py-2 text-paper" maxlength="300" />
      </label>
      <p v-if="message" class="text-sm text-glow" role="alert">{{ message }}</p>
      <button class="btn-primary h-11" type="submit" :disabled="pending">提交</button>
    </form>
  </div>
</template>
