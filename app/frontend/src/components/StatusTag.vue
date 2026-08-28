<script setup>
// 订单状态 → 徽章（16 态配色）
const props = defineProps({ status: String })
const MAP = {
  draft: ['草稿', 'tag-ink'], modeling: ['模型处理中', 'tag-info'],
  val1_pending: ['Val1审核中', 'tag-info'], val1_failed: ['Val1未通过', 'tag-fail'],
  val1_appeal: ['Val1申诉中', 'tag-warn'], slicing: ['切片中', 'tag-info'],
  val2_pending: ['Val2审核中', 'tag-warn'], val2_failed: ['Val2未通过', 'tag-fail'],
  queued: ['等待打印', 'tag-info'], printing: ['打印中', 'tag-warn'],
  val3_pending: ['等待验收', 'tag-warn'], val3_failed: ['Val3未通过', 'tag-fail'],
  rework: ['重新处理', 'tag-warn'], settlement: ['成本核算中', 'tag-info'],
  completed: ['已完成', 'tag-pass'], terminated: ['已终止', 'tag-fail'],
}
const [label, cls] = MAP[props.status] || [props.status, 'tag-ink']
</script>

<template><span class="tag" :class="cls">{{ label }}</span></template>
