<script setup lang="ts">
import type { NuxtError } from '#app'

defineProps<{ error: NuxtError }>()
</script>

<template>
  <main class="grid min-h-dvh place-items-center bg-ink px-5 text-paper">
    <div class="text-center">
      <img src="/logo.jpg" alt="Violet Z" class="mx-auto h-24 w-24 rounded-2xl object-cover" />
      <p class="mt-6 text-mute">{{ error.statusCode }}</p>
      <NuxtLink class="btn-primary mt-6" to="/">返回首页</NuxtLink>
    </div>
  </main>
</template>
