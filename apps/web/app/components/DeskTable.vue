<script setup lang="ts">
const props = defineProps<{ title: string; view: string }>()

interface DeskPayload {
  columns: string[]
  rows: string[][]
}

const { data, error } = await useAsyncData(`desk-${props.view}`, () => $fetch<DeskPayload>(`/api/desk/${props.view}`))
</script>

<template>
  <section>
    <h1 class="text-3xl">{{ title }}</h1>
    <p v-if="error" class="mt-6 text-glow" role="alert">暂时读不到数据</p>
    <p v-else-if="data && data.rows.length === 0" class="mt-6 text-mute">还没有记录</p>
    <div v-else-if="data" class="mt-6 overflow-x-auto rounded-2xl border border-line">
      <table class="w-full min-w-[40rem] text-left text-sm">
        <thead class="bg-panel text-mute">
          <tr>
            <th v-for="column in data.columns" :key="column" class="px-3 py-2 font-normal">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in data.rows" :key="index" class="border-t border-line">
            <td v-for="(cell, cellIndex) in row" :key="cellIndex" class="max-w-xs truncate px-3 py-2">{{ cell }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
