<script setup lang="ts">
const session = useSessionStore()
</script>

<template>
  <header class="border-b border-line">
    <div class="shell flex h-20 items-center justify-between gap-4">
      <NuxtLink to="/" class="flex shrink-0 items-center gap-3">
        <img src="/logo.jpg" alt="Violet Print" class="h-14 w-14 rounded-xl object-cover" />
        <span class="hidden leading-tight sm:block">
          Violet Print
          <small class="block text-xs text-mute">TEAM 6940</small>
        </span>
      </NuxtLink>
      <nav class="flex items-center gap-5">
        <NuxtLink to="/campaigns" class="navlink">活动</NuxtLink>
        <NuxtLink to="/models" class="navlink">模型</NuxtLink>
        <NuxtLink to="/orders" class="navlink">需求</NuxtLink>
        <NuxtLink to="/create" class="navlink">新建</NuxtLink>
        <NuxtLink to="/manual" class="navlink">手册</NuxtLink>
        <NuxtLink v-if="session.isStaff" to="/admin" class="navlink">管理</NuxtLink>
        <NuxtLink v-if="session.user" to="/account" class="hidden text-sm text-mute sm:inline">{{ session.user.name }}</NuxtLink>
        <form method="post" action="/api/oauth/logout">
          <button class="navlink" type="submit">退出</button>
        </form>
      </nav>
    </div>
  </header>
</template>
