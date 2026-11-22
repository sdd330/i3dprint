<script setup lang="ts">
import type { HomePayload } from '#shared/print'
import { campaignStatusLabel, orderStatusLabel } from '#shared/print'

const { data, error } = await useAsyncData('home', () => $fetch<HomePayload>('/api/home'))
useSeoMeta({ title: 'Violet Print', description: 'TEAM 6940 校园三维打印' })
</script>

<template>
  <div>
    <section class="grid items-center gap-8 md:grid-cols-[auto_1fr]">
      <img src="/logo.jpg" alt="" class="h-36 w-36 rounded-3xl object-cover" />
      <div>
        <h1 class="text-4xl leading-tight">Violet Print</h1>
        <p class="mt-3 max-w-xl text-mute">创建打印需求，负责人按清单执行。</p>
      </div>
    </section>
    <p v-if="error" class="mt-8 text-glow" role="alert">暂时读不到数据</p>
    <template v-else-if="data">
      <dl class="mt-10 grid gap-4 sm:grid-cols-3">
        <div class="card">
          <dt class="text-sm text-mute">活动</dt>
          <dd class="mt-2 text-3xl">{{ data.campaignCount }}</dd>
        </div>
        <div class="card">
          <dt class="text-sm text-mute">模型</dt>
          <dd class="mt-2 text-3xl">{{ data.modelCount }}</dd>
        </div>
        <div class="card">
          <dt class="text-sm text-mute">需求</dt>
          <dd class="mt-2 text-3xl">{{ data.orderCount }}</dd>
        </div>
      </dl>
      <section class="mt-10">
        <h2 class="text-xl">最近需求</h2>
        <p v-if="data.orders.length === 0" class="mt-4 text-mute">还没有记录</p>
        <ul v-else class="mt-4 divide-y divide-line overflow-hidden rounded-2xl border border-line">
          <li v-for="order in data.orders" :key="order.code">
            <NuxtLink class="flex items-center justify-between gap-4 px-4 py-3 hover:bg-panel" :to="`/orders/${order.code}`">
              <span>{{ order.name }}</span>
              <StatusPill :label="orderStatusLabel(order.status)" />
            </NuxtLink>
          </li>
        </ul>
      </section>
      <section class="mt-10">
        <h2 class="text-xl">活动</h2>
        <p v-if="data.campaigns.length === 0" class="mt-4 text-mute">还没有记录</p>
        <ul v-else class="mt-4 grid gap-4">
          <li v-for="campaign in data.campaigns" :key="campaign.code" class="card flex items-center justify-between gap-4">
            <span>{{ campaign.name }}</span>
            <StatusPill :label="campaignStatusLabel(campaign.status)" />
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>
