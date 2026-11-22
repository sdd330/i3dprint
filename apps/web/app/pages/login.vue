<script setup lang="ts">
definePageMeta({ layout: false })

const route = useRoute()
const errorCode = computed(() => (typeof route.query.error === 'string' ? route.query.error : ''))
const message = computed(() => {
  if (errorCode.value === 'locked') return '尝试过多，请稍后再来'
  if (errorCode.value === 'expired') return '登录已过期，请重试'
  if (errorCode.value === '1') return '账号或口令不正确'
  return ''
})

useSeoMeta({ title: '登录 · Violet Z', description: 'Violet Z 登录' })
</script>

<template>
  <main class="grid min-h-dvh place-items-center bg-ink px-5 text-paper">
    <section class="w-full max-w-sm">
      <img src="/logo.jpg" alt="Violet Z" class="mx-auto h-28 w-28 rounded-2xl object-cover" />
      <h1 class="mt-6 text-center text-2xl">登录</h1>
      <p v-if="message" class="mt-3 text-center text-sm text-glow" role="alert">{{ message }}</p>
      <form class="mt-6 grid gap-4" method="post" action="/api/oauth/authorize">
        <label class="grid gap-2 text-sm text-mute">
          账号
          <input
            class="h-11 rounded-xl border border-line bg-panel px-3 text-paper"
            name="username"
            autocomplete="username"
            required
            maxlength="32"
          />
        </label>
        <label class="grid gap-2 text-sm text-mute">
          口令
          <input
            class="h-11 rounded-xl border border-line bg-panel px-3 text-paper"
            name="password"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <button class="btn-primary" type="submit">进入</button>
      </form>
    </section>
  </main>
</template>
