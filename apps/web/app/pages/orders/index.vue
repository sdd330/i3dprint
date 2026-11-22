<script setup lang="ts">
import type { OrderItem } from '#shared/print'
import { formatDate, orderStatusLabel, safeColor } from '#shared/print'

const filter = useOrderFilterStore()
const { data, error } = await useAsyncData('orders', () => $fetch<OrderItem[]>('/api/orders'))
const materials = computed(() => [...new Set((data.value ?? []).map((order) => order.materialNo))])
const visible = computed(() =>
  (data.value ?? []).filter((order) => {
    if (filter.status && order.status !== filter.status) return false
    if (filter.materialNo && order.materialNo !== filter.materialNo) return false
    return true
  }),
)

useSeoMeta({ title: '需求 · Violet Z' })
</script>

<template>
  <div>
    <div class="flex flex-wrap items-end justify-between gap-4">
      <h1 class="text-3xl">需求</h1>
      <div class="flex gap-3">
        <label class="grid gap-1 text-xs text-mute">
          状态
          <select v-model.number="filter.status" class="h-10 rounded-xl border border-line bg-panel px-3 text-sm text-paper">
            <option :value="0">全部</option>
            <option :value="1">草稿</option>
            <option :value="2">申诉</option>
            <option :value="3">切片</option>
            <option :value="4">待核验</option>
            <option :value="5">核验失败</option>
          </select>
        </label>
        <label class="grid gap-1 text-xs text-mute">
          耗材
          <select v-model="filter.materialNo" class="h-10 rounded-xl border border-line bg-panel px-3 text-sm text-paper">
            <option value="">全部</option>
            <option v-for="material in materials" :key="material" :value="material">{{ material }}</option>
          </select>
        </label>
      </div>
    </div>
    <p v-if="error" class="mt-6 text-glow" role="alert">暂时读不到数据</p>
    <p v-else-if="visible.length === 0" class="mt-6 text-mute">还没有记录</p>
    <ul v-else class="mt-6 grid gap-3">
      <li v-for="order in visible" :key="order.code">
        <NuxtLink class="card flex items-center justify-between gap-4" :to="`/orders/${order.code}`">
          <span class="flex items-center gap-3">
            <span class="h-3 w-3 rounded-full" :style="{ background: safeColor(order.color) }" />
            <span>
              <span class="block">{{ order.name }}</span>
              <span class="text-sm text-mute">{{ order.campaignName }} · {{ order.materialNo }} · {{ formatDate(order.createdAt) }}</span>
            </span>
          </span>
          <StatusPill :label="orderStatusLabel(order.status)" />
        </NuxtLink>
      </li>
    </ul>
  </div>
</template>
