<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore, useAuthStore } from '@/stores'
import { api } from '@/api'
import StatusTag from '@/components/StatusTag.vue'

const app = useAppStore()
const auth = useAuthStore()
const router = useRouter()
const myOrders = ref([])

const campaign = computed(() => app.meta?.campaign)
const compliance = computed(() => app.meta?.compliance || {})
// 收费信息暂时隐去（用户要求）——后端 flow.billing_visible 控制，恢复时置 true 即可
const billingVisible = computed(() => app.billingVisible)

const STATUS_META = {
  待开放: ['即将开放', 'tag-ink'], 开放中: ['开放中 · 可接单', 'tag-pass'],
  收尾中: ['收尾中 · 停止接单', 'tag-warn'], 已归档: ['已归档', 'tag-ink'],
}
const [campLabel, campCls] = STATUS_META[campaign?.value?.status] || ['', 'tag-ink']
const chain = ['创建', '摆放', 'Val1', '打印需求', '打印', 'Val3', '核算']

onMounted(async () => {
  await app.loadMeta()
  if (auth.isLoggedIn) {
    myOrders.value = (await api.get('/orders')).orders
  }
})
</script>

<template>
  <div class="page">
    <div style="display: grid; grid-template-columns: 1.4fr 1fr; gap: 20px" class="home-grid">
      <!-- 左：活动主卡 -->
      <div class="card" style="padding: 28px">
        <div style="display: flex; justify-content: space-between; align-items: start; gap: 12px">
          <div>
            <h1 style="margin: 0 0 8px; font-size: 26px">{{ campaign?.name || '活动加载中…' }}</h1>
            <span class="tag" :class="campCls">{{ campLabel }}</span>
            <span class="tag tag-ink" style="margin-left: 8px">单场 ≤ {{ campaign?.max_participants }} 人</span>
          </div>
          <div style="text-align: right; font-family: var(--mono); font-size: 12px" class="muted">
            <div>活动密码（取件用）</div>
            <div style="font-size: 18px; font-weight: 700; color: var(--accent)">{{ campaign?.password }}</div>
          </div>
        </div>
        <p style="color: var(--ink-soft); margin: 10px 0 0">{{ compliance?.statement }}</p>

        <div style="display: flex; gap: 12px; margin-top: 22px">
          <el-button type="primary" size="large" style="flex: 1" @click="router.push('/create')">
            我要打印
          </el-button>
          <el-button v-if="app.flow.ai_modeling" size="large" style="flex: 1" @click="router.push('/ai')">AI 建模</el-button>
          <el-button size="large" style="flex: 1" @click="router.push('/orders')">我的订单</el-button>
        </div>

        <!-- 主链说明 -->
        <el-divider content-position="left"><span style="font-weight: 600">打印主链</span></el-divider>
        <div style="display: flex; gap: 0; flex-wrap: wrap; font-size: 12.5px" class="muted">
          <template v-for="(s, i) in chain" :key="s">
            <span style="white-space: nowrap">{{ s }}</span>
            <span v-if="i < chain.length - 1" style="margin: 0 6px; color: var(--line)">→</span>
          </template>
        </div>
        <div style="margin-top: 10px; font-size: 12.5px" class="muted">
          Val1 自动审核（有潜在问题就标记转人工复核，不退回） · 通过后填打印需求生成清单 · Val3 管实物合不合格
        </div>
        <div style="margin-top: 6px; font-size: 12.5px" class="muted">
          当前版本暂不提供在线切片与 Val2 切片核验：负责人按打印清单在切片软件中执行。
        </div>
      </div>

      <!-- 右：运营信息 -->
      <div style="display: flex; flex-direction: column; gap: 16px">
        <div class="card" style="padding: 16px">
          <div style="font-weight: 700; margin-bottom: 8px">📦 取件信息（§16.1）</div>
          <div style="font-size: 13px" class="muted">
            {{ compliance?.pickup_location }}<br />
            时间：{{ compliance?.pickup_window }}<br />
            凭证：活动密码 + 需求编号
          </div>
        </div>
        <div class="card" style="padding: 16px">
          <div style="font-weight: 700; margin-bottom: 8px">🧑‍🏫 线下负责人（§16.2）</div>
          <div v-for="g in compliance?.contacts || []" :key="g.grade" style="font-size: 13px; margin-bottom: 6px" class="muted">
            <b style="color: var(--ink)">{{ g.grade }}</b>：{{ g.members.join(' / ') }}
          </div>
        </div>
        <div class="card" style="padding: 16px" v-if="billingVisible">
          <div style="font-weight: 700; margin-bottom: 8px">🧾 费用构成（§11）</div>
          <div style="font-size: 13px" class="muted">
            耗材费 = 成本价 × 重量 × 系数（+ 换料补偿）<br />
            维护费（打印头磨损摊分）+ API 用量费<br />
            <b style="color: var(--accent)">非营利，活动结束统一核算收款</b>
          </div>
        </div>
      </div>
    </div>

    <!-- 我的最近订单 -->
    <div v-if="auth.isLoggedIn && myOrders.length" style="margin-top: 24px">
      <h3 style="margin: 0 0 12px">我的最近订单</h3>
      <div class="card" style="padding: 0; overflow: hidden">
        <el-table :data="myOrders.slice(0, 5)" style="width: 100%">
          <el-table-column prop="id" label="编号" width="90">
            <template #default="{ row }"><span class="mono">O{{ row.id }}</span></template>
          </el-table-column>
          <el-table-column prop="name" label="需求" />
          <el-table-column label="状态" width="150">
            <template #default="{ row }"><StatusTag :status="row.status" /></template>
          </el-table-column>
          <el-table-column v-if="billingVisible" label="费用" width="110">
            <template #default="{ row }"><span class="amount">¥{{ row.cost?.total?.toFixed(2) }}</span></template>
          </el-table-column>
          <el-table-column label="" width="90">
            <template #default="{ row }">
              <el-button link type="primary" @click="router.push(`/orders/${row.id}`)">追踪</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>
