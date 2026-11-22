<script setup lang="ts">
import type { ModelItem } from '#shared/print'
import { modelKindLabel } from '#shared/print'

const { data, error } = await useAsyncData('models', () => $fetch<ModelItem[]>('/api/models'))
useSeoMeta({ title: '模型 · Violet Z' })
</script>

<template>
  <div>
    <h1 class="text-3xl">模型</h1>
    <p v-if="error" class="mt-6 text-glow" role="alert">暂时读不到数据</p>
    <p v-else-if="!data?.length" class="mt-6 text-mute">还没有记录</p>
    <ul v-else class="mt-6 grid gap-4">
      <li v-for="model in data" :key="model.code" class="card">
        <div class="flex items-center justify-between gap-4">
          <NuxtLink class="text-xl hover:text-glow" :to="`/models/${model.code}`">{{ model.name }}</NuxtLink>
          <StatusPill :label="modelKindLabel(model.kind)" />
        </div>
        <p class="mt-3 text-sm text-mute">{{ model.summary || '没有描述' }}</p>
      </li>
    </ul>
  </div>
</template>
