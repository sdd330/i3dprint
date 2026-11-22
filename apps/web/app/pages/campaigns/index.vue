<script setup lang="ts">
import type { Campaign } from '#shared/print'
import { campaignStatusLabel, formatDate } from '#shared/print'

const { data, error } = await useAsyncData('campaigns', () => $fetch<Campaign[]>('/api/campaigns'))
useSeoMeta({ title: '活动 · Violet Z' })
</script>

<template>
  <div>
    <h1 class="text-3xl">活动</h1>
    <p v-if="error" class="mt-6 text-glow" role="alert">暂时读不到数据</p>
    <p v-else-if="!data?.length" class="mt-6 text-mute">还没有记录</p>
    <ul v-else class="mt-6 grid gap-4">
      <li v-for="campaign in data" :key="campaign.code" class="card">
        <div class="flex items-center justify-between gap-4">
          <h2 class="text-xl">{{ campaign.name }}</h2>
          <StatusPill :label="campaignStatusLabel(campaign.status)" />
        </div>
        <p class="mt-3 text-sm text-mute">
          {{ formatDate(campaign.openDate) }} 至 {{ formatDate(campaign.closeDate) }}
          · 上限 {{ campaign.maxParticipants }} · 需求 {{ campaign.orderCount }}
        </p>
        <p v-if="campaign.remark" class="mt-2 text-sm">{{ campaign.remark }}</p>
      </li>
    </ul>
  </div>
</template>
