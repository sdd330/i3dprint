<script setup>
// 打印主链状态轴（签名元素）
// 2026-10：在线切片 + Val2 暂缓 → 主链改为「创建 → 摆放 → Val1 → 打印需求 → 打印 → Val3 → 核算」
import { computed } from 'vue'
const props = defineProps({ status: String })

const CHAIN = [
  { key: 'create', label: '创建' },
  { key: 'place', label: '摆放' },
  { key: 'val1', label: 'Val1' },
  { key: 'require', label: '打印需求' },
  { key: 'print', label: '打印' },
  { key: 'val3', label: 'Val3' },
  { key: 'cost', label: '核算' },
]

// 每个订单状态对应的主链进度：[已完成步骤数, 当前步骤 index]
const STEP_OF = {
  draft: [-1, 0], modeling: [0, 1],
  val1_pending: [1, 2], val1_review: [1, 2], val1_failed: [1, 2],
  print_config: [2, 3],
  queued: [3, 4], printing: [3, 4],
  val3_pending: [4, 5], val3_failed: [4, 5],
  rework: [3, 4], settlement: [5, 6], completed: [6, -1], terminated: [3, 4],
  // 旧流程（历史数据）
  val1_appeal: [1, 2], slicing: [2, 3], val2_pending: [2, 3], val2_failed: [2, 3],
}
const state = computed(() => {
  const [done, active] = STEP_OF[props.status] || [0, 0]
  return { done, active }
})
</script>

<template>
  <div class="chain">
    <template v-for="(s, i) in CHAIN" :key="s.key">
      <div class="chain-step"
           :class="{ done: i < state.done, active: i === state.active && status !== 'terminated', failed: status === 'terminated' && i === state.active }">
        <span class="chain-dot" />
        <span class="chain-label">{{ s.label }}</span>
      </div>
      <span v-if="i < CHAIN.length - 1" class="chain-bar" />
    </template>
  </div>
</template>
