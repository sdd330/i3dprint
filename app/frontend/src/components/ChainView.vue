<script setup>
// 打印主链状态轴（签名元素）：创建→摆放→Val1→耗材/参数→切片→Val2→打印→Val3→核算
import { computed } from 'vue'
const props = defineProps({ status: String })

const CHAIN = [
  { key: 'create', label: '创建' },
  { key: 'place', label: '摆放' },
  { key: 'val1', label: 'Val1' },
  { key: 'params', label: '耗材/参数' },
  { key: 'slice', label: '切片' },
  { key: 'val2', label: 'Val2' },
  { key: 'print', label: '打印' },
  { key: 'val3', label: 'Val3' },
  { key: 'cost', label: '核算' },
]
// 每个订单状态对应的主链进度（index 完成数，activeIndex 当前步骤）
const STEP_OF = {
  draft: [-1, 0], modeling: [0, 1], val1_pending: [1, 2], val1_failed: [1, 2],
  val1_appeal: [1, 2], slicing: [4, 5], val2_pending: [4, 5], val2_failed: [4, 5],
  queued: [5, 6], printing: [5, 6], val3_pending: [6, 7], val3_failed: [6, 7],
  rework: [4, 5], settlement: [7, 8], completed: [8, -1], terminated: [5, 6],
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
