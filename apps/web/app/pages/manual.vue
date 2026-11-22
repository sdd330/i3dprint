<script setup lang="ts">
useSeoMeta({ title: '手册 · Violet Print' })

const steps = [
  '登录后进入当前活动。',
  '创建打印需求，写清名称、材料和给执行人的备注。',
  '负责人在工作台查看打印清单，完成切片和上机。',
  '打印完成后在需求详情里查看任务状态。',
]
</script>

<template>
  <article class="max-w-2xl">
    <h1 class="text-3xl">使用手册</h1>
    <p class="mt-3 text-mute">Violet Print，TEAM 6940 校园三维打印。在线切片和 AI 建模保持关闭。</p>
    <ol class="mt-8 grid gap-4">
      <li v-for="(step, index) in steps" :key="step" class="card">
        <span class="text-mute">{{ index + 1 }}</span>
        <p class="mt-2">{{ step }}</p>
      </li>
    </ol>
  </article>
</template>
