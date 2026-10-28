<script setup>
// 操作日志（§13.4）：登录/创建/审核/打印/验收/费用 均记录
import { ref, onMounted, computed } from 'vue'
import { api } from '@/api'
import { useAppStore } from '@/stores'

const app = useAppStore()
const billingVisible = computed(() => app.billingVisible)

// 后端暂未提供 audit log 列表 API，用配置审计 + 提示补充
const audits = ref([])
const logs = ref([])

onMounted(async () => {
  if (!app.meta) app.loadMeta().catch(() => {})
  audits.value = (await api.get('/admin/config/audits')).audits
  logs.value = (await api.get('/admin/audit-logs')).logs
})
</script>

<template>
  <div class="page" style="max-width: 980px">
    <h1 class="page-title">审计与可追溯</h1>
    <p class="page-sub">核心数据不可无痕篡改：模型版本、打印清单、审核记录均保留历史（§13）</p>

    <div class="card" style="margin-bottom: 16px">
      <b>配置修改审计</b>
      <el-table :data="audits" size="small" style="margin-top: 8px">
        <el-table-column label="时间" width="160">
          <template #default="{ row }"><span class="mono" style="font-size: 11px">{{ row.at }}</span></template>
        </el-table-column>
        <el-table-column prop="scope" label="范围" width="90" />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="operator" label="操作人" width="100" />
        <el-table-column label="旧值" prop="old" show-overflow-tooltip />
        <el-table-column label="新值" prop="new" show-overflow-tooltip />
      </el-table>
    </div>

    <div class="card" style="margin-bottom: 16px">
      <b>操作日志（§13.4）</b>
      <el-table :data="logs" size="small" style="margin-top: 8px">
        <el-table-column label="时间" width="160">
          <template #default="{ row }"><span class="mono" style="font-size: 11px">{{ row.at }}</span></template>
        </el-table-column>
        <el-table-column prop="username" label="操作人" width="100" />
        <el-table-column prop="action" label="动作" width="160" />
        <el-table-column prop="target" label="对象" width="120" />
        <el-table-column prop="detail" label="详情" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP" width="130" />
      </el-table>
    </div>

    <div class="card">
      <b>可追溯性设计</b>
      <el-descriptions :column="1" border size="small" style="margin-top: 8px">
        <el-descriptions-item label="模型版本">修改模型生成新版本，不覆盖历史（§13.1）</el-descriptions-item>
        <el-descriptions-item label="打印清单">记录模型版本 / 材料 / 强度 / 工艺参数（§13.2；在线切片暂缓）</el-descriptions-item>
        <el-descriptions-item label="审核结果">Val1 / Val3 审核人、时间、版本均记录（§13.3；Val2 切片核验暂缓）</el-descriptions-item>
        <el-descriptions-item v-if="billingVisible" label="费用流水">append-only，每笔关联活动/需求/打印任务并注明原因（§13.5）</el-descriptions-item>
      </el-descriptions>
    </div>
  </div>
</template>
