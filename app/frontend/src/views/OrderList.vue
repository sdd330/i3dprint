<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import ChainView from '@/components/ChainView.vue'

const router = useRouter()
const orders = ref([])
const loading = ref(true)
const filter = ref('')
const FILTERS = [['', '全部'], ['active', '进行中'], ['completed', '已完成'], ['terminated', '已终止']]

const list = computed(() => {
  let l = orders.value
  if (filter.value === 'active') l = l.filter(o => !['completed', 'terminated'].includes(o.status))
  if (filter.value === 'completed') l = l.filter(o => o.status === 'completed')
  if (filter.value === 'terminated') l = l.filter(o => o.status === 'terminated')
  return l
})

onMounted(async () => {
  try {
    orders.value = (await api.get('/orders')).orders
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <h1 class="page-title">我的订单</h1>
    <p class="page-sub">每个打印需求都在所属活动中独立流转（两级状态机：活动 4 态 × 订单 16 态）</p>

    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button v-for="[k, label] in FILTERS" :key="k" :value="k">{{ label }}</el-radio-button>
      </el-radio-group>
      <el-button type="primary" @click="router.push('/create')">+ 新建需求</el-button>
    </div>

    <el-table v-loading="loading" :data="list" style="width: 100%">
      <el-table-column label="需求" min-width="200">
        <template #default="{ row }">
          <div style="font-weight: 600">{{ row.name }}</div>
          <div class="muted mono" style="font-size: 11.5px">O{{ row.id }} · {{ row.created_at?.slice(0, 16) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="160">
        <template #default="{ row }"><StatusTag :status="row.status" /></template>
      </el-table-column>
      <el-table-column label="主链进度" min-width="420">
        <template #default="{ row }"><ChainView :status="row.status" /></template>
      </el-table-column>
      <el-table-column label="费用" width="100">
        <template #default="{ row }"><span class="amount">¥{{ row.cost?.total?.toFixed(2) }}</span></template>
      </el-table-column>
      <el-table-column label="" width="90">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/orders/${row.id}`)">查看</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="还没有打印需求，点右上角新建一个吧" />
      </template>
    </el-table>
  </div>
</template>
