<script setup lang="ts">
import type { ModelDetail } from '#shared/print'
import { modelKindLabel } from '#shared/print'

const route = useRoute()
const code = computed(() => String(route.params.code))
const { data, error } = await useAsyncData(
  () => `model-${code.value}`,
  () => $fetch<ModelDetail>(`/api/models/${code.value}`),
)
useSeoMeta({ title: () => (data.value ? `${data.value.name} · Violet Z` : '模型 · Violet Z') })
</script>

<template>
  <div>
    <p v-if="error" class="text-glow" role="alert">{{ error.statusCode === 404 ? '没有这条记录' : '暂时读不到数据' }}</p>
    <article v-else-if="data">
      <div class="flex items-center justify-between gap-4">
        <h1 class="text-3xl">{{ data.name }}</h1>
        <StatusPill :label="modelKindLabel(data.kind)" />
      </div>
      <p class="mt-6 whitespace-pre-wrap text-mute">{{ data.description || '没有描述' }}</p>
    </article>
  </div>
</template>
