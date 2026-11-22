<script setup lang="ts">
definePageMeta({ layout: false })
useSeoMeta({ title: '离线 · Violet Z' })

const online = ref(true)
onMounted(() => {
  online.value = navigator.onLine
  const sync = () => {
    online.value = navigator.onLine
  }
  window.addEventListener('online', sync)
  window.addEventListener('offline', sync)
  onBeforeUnmount(() => {
    window.removeEventListener('online', sync)
    window.removeEventListener('offline', sync)
  })
})
</script>

<template>
  <main class="grid min-h-dvh place-items-center bg-ink px-5 text-paper">
    <div class="text-center">
      <img src="/logo.jpg" alt="Violet Z" class="mx-auto h-24 w-24 rounded-2xl object-cover" />
      <h1 class="mt-6 text-2xl">{{ online ? '已重新联网' : '当前离线' }}</h1>
      <p class="mt-3 text-mute">活动、需求和登录需要网络。手册与已缓存页面仍可打开。</p>
      <div class="mt-6 flex justify-center gap-3">
        <NuxtLink class="btn-primary" to="/">返回首页</NuxtLink>
        <NuxtLink class="btn-ghost" to="/manual">打开手册</NuxtLink>
      </div>
    </div>
  </main>
</template>
