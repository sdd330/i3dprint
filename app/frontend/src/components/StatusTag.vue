<script setup>
// 订单状态 → 徽章
// 2026-10：Val1 不再自动退回，改为「标记 + 人工复核」；在线切片/Val2 暂缓
const props = defineProps({ status: String })
const MAP = {
  draft: ['草稿', 'tag-ink'], modeling: ['模型处理中', 'tag-info'],
  val1_pending: ['Val1 自动审核中', 'tag-info'],
  val1_review: ['Val1 已标记 · 待人工复核', 'tag-warn'],
  val1_failed: ['需修改模型（人工判定）', 'tag-fail'],
  print_config: ['待填打印需求', 'tag-info'],
  queued: ['已入打印清单', 'tag-info'], printing: ['打印中', 'tag-warn'],
  val3_pending: ['等待验收', 'tag-warn'], val3_failed: ['Val3 未通过', 'tag-fail'],
  rework: ['重新处理', 'tag-warn'], settlement: ['待确认完成', 'tag-info'],
  completed: ['已完成', 'tag-pass'], terminated: ['已终止', 'tag-fail'],
  // 旧流程（历史数据）
  val1_appeal: ['Val1 警告/申诉中（旧）', 'tag-warn'], slicing: ['切片中（旧）', 'tag-info'],
  val2_pending: ['Val2 审核中（旧）', 'tag-warn'], val2_failed: ['Val2 未通过（旧）', 'tag-fail'],
}
const [label, cls] = MAP[props.status] || [props.status, 'tag-ink']
</script>

<template><span class="tag" :class="cls">{{ label }}</span></template>
