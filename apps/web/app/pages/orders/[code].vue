<script setup lang="ts">
import type { OrderDetail } from '#shared/print'
import { formatDate, formatWeight, jobStatusLabel, orderStatusLabel, safeColor } from '#shared/print'

const route = useRoute()
const code = computed(() => String(route.params.code))
const { data, error } = await useAsyncData(
  () => `order-${code.value}`,
  () => $fetch<OrderDetail>(`/api/orders/${code.value}`),
)
useSeoMeta({ title: () => (data.value ? `${data.value.name} · Violet Z` : '需求 · Violet Z') })
</script>

<template>
  <div>
    <p v-if="error" class="text-glow" role="alert">{{ error.statusCode === 404 ? '没有这条记录' : '暂时读不到数据' }}</p>
    <article v-else-if="data">
      <div class="flex items-center justify-between gap-4">
        <h1 class="text-3xl">{{ data.name }}</h1>
        <StatusPill :label="orderStatusLabel(data.status)" />
      </div>
      <NuxtLink class="btn mt-4 inline-flex" :to="`/orders/${data.code}/print`">打印需求</NuxtLink>
      <p class="mt-3 text-sm text-mute">{{ data.campaignName }} · {{ formatDate(data.createdAt) }}</p>
      <dl class="mt-6 grid gap-4 sm:grid-cols-3">
        <div class="card">
          <dt class="text-sm text-mute">耗材</dt>
          <dd class="mt-2 flex items-center gap-2">
            <span class="h-3 w-3 rounded-full" :style="{ background: safeColor(data.color) }" />
            {{ data.materialNo }}
          </dd>
        </div>
        <div class="card">
          <dt class="text-sm text-mute">模型</dt>
          <dd class="mt-2">{{ data.modelName || '未关联' }}</dd>
        </div>
        <div class="card">
          <dt class="text-sm text-mute">自备耗材</dt>
          <dd class="mt-2">{{ data.selfFilament ? '是' : '否' }}</dd>
        </div>
      </dl>
      <p v-if="data.filamentNote" class="mt-6 whitespace-pre-wrap text-mute">{{ data.filamentNote }}</p>
      <h2 class="mt-10 text-xl">打印任务</h2>
      <p v-if="data.jobs.length === 0" class="mt-4 text-mute">还没有打印任务</p>
      <ul v-else class="mt-4 grid gap-3">
        <li v-for="job in data.jobs" :key="job.seq" class="card">
          <div class="flex items-center justify-between gap-4">
            <span>第 {{ job.seq }} 次 · {{ job.printerNo || '未分配打印机' }}</span>
            <StatusPill :label="jobStatusLabel(job.status)" />
          </div>
          <p class="mt-2 text-sm text-mute">
            预估 {{ formatWeight(job.estWeightMg) }} · 实际 {{ formatWeight(job.actualWeightMg) }}
          </p>
        </li>
      </ul>
    </article>
  </div>
</template>
