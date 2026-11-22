<script setup lang="ts">
defineProps<{ label: string }>()
</script>

<template>
  <span class="inline-flex rounded-full border border-line px-2.5 py-1 text-xs text-glow">{{ label }}</span>
</template>
