<script setup lang="ts">
const pwa = usePWA()
const showInstall = computed(() => Boolean(pwa?.showInstallPrompt && !pwa.isPWAInstalled))
const showUpdate = computed(() => Boolean(pwa?.needRefresh))
const showReady = computed(() => Boolean(pwa?.offlineReady && !showUpdate.value && !showInstall.value))
</script>

<template>
  <div
    v-if="pwa && (showInstall || showUpdate || showReady)"
    class="fixed inset-x-0 bottom-0 z-50 border-t border-line bg-panel/95 px-5 py-4 backdrop-blur"
  >
    <div class="shell flex flex-wrap items-center justify-between gap-3">
      <p v-if="showUpdate" class="text-sm">有新版本可用</p>
      <p v-else-if="showInstall" class="text-sm">安装到主屏幕，离线也能打开手册与缓存页</p>
      <p v-else class="text-sm">已可离线使用</p>
      <div class="flex gap-3">
        <button
          v-if="showUpdate"
          class="btn-primary"
          type="button"
          @click="pwa?.updateServiceWorker(true)"
        >
          更新
        </button>
        <template v-else-if="showInstall">
          <button class="btn-primary" type="button" @click="pwa?.install()">安装</button>
          <button class="btn-ghost" type="button" @click="pwa?.cancelInstall()">稍后</button>
        </template>
        <button v-else class="btn-ghost" type="button" @click="pwa?.cancelPrompt()">知道了</button>
      </div>
    </div>
  </div>
</template>
