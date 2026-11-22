<script setup lang="ts">
definePageMeta({ layout: false })
useSeoMeta({ title: '离线 · Violet Z' })
</script>

<template>
  <main class="grid min-h-dvh place-items-center bg-ink px-5 text-paper">
    <div class="text-center">
      <img src="/logo.jpg" alt="Violet Z" class="mx-auto h-24 w-24 rounded-2xl object-cover" />
      <h1 class="mt-6 text-2xl">当前离线</h1>
      <NuxtLink class="btn-primary mt-6" to="/">返回</NuxtLink>
    </div>
  </main>
</template>
