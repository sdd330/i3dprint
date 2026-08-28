<script setup>
// 配置中心（决策清单 §14）：默认模板 + 活动参数副本 + 修改审计
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const CATS = [
  { key: 'activity', name: '活动参数', hint: '人数上限 / 申诉上限 / 公告' },
  { key: 'fee', name: '费用参数', hint: '材料价格表 / 换料补偿 / 维护费 / API单价' },
  { key: 'val1', name: 'Val1 阈值', hint: '壁厚 / 悬垂 / 打印范围 / 检查项' },
  { key: 'presets', name: '打印参数档', hint: '快速/标准/精细，参考 OrcaSlicer' },
  { key: 'print', name: '打印/设备', hint: '重打比例 / 队列策略 / 异常重排' },
  { key: 'compliance', name: '合规配置', hint: '禁止清单 / 平台声明 / 取件 / 负责人' },
  { key: 'qa', name: '站娘配置', hint: 'System Prompt / 过滤词' },
]
const scope = ref('template') // template | campaign
const active = ref('val1')
const template = ref(null)
const campaignCfg = ref(null)
const editing = ref('')
const audits = ref([])

const current = computed(() => {
  const src = scope.value === 'template' ? template.value?.data : campaignCfg.value
  return src?.[active.value]
})

async function load() {
  template.value = (await api.get('/admin/config/template')).template
  const meta = await api.get('/meta/bootstrap')
  campaignCfg.value = (await api.get(`/admin/config/campaign/${meta.campaign.id}`)).config
  audits.value = (await api.get('/admin/config/audits')).audits
  editing.value = JSON.stringify(current.value, null, 2)
}

function switchScope(s) {
  scope.value = s
  editing.value = JSON.stringify(current.value, null, 2)
}
function switchCat(k) {
  active.value = k
  editing.value = JSON.stringify(current.value, null, 2)
}

async function save() {
  let data
  try {
    data = JSON.parse(editing.value)
  } catch {
    return ElMessage.error('JSON 格式错误，无法保存')
  }
  const meta = await api.get('/meta/bootstrap')
  const url = scope.value === 'template'
    ? `/admin/config/template/${active.value}`
    : `/admin/config/campaign/${meta.campaign.id}/${active.value}`
  await api.put(url, { data })
  ElMessage.success('已保存（改动即时生效，已记录审计）')
  load()
}
</script>

<template>
  <div class="page">
    <h1 class="page-title">配置中心</h1>
    <p class="page-sub">默认模板（全局基线）与活动参数副本（可选继承）· 所有修改留审计 · 改动即时生效</p>

    <div style="display: grid; grid-template-columns: 220px 1fr; gap: 16px">
      <div style="display: flex; flex-direction: column; gap: 8px">
        <el-radio-group v-model="scope" style="margin-bottom: 8px">
          <el-radio-button value="template">默认模板</el-radio-button>
          <el-radio-button value="campaign">当前活动</el-radio-button>
        </el-radio-group>
        <el-menu :default-active="active" @select="switchCat">
          <el-menu-item v-for="c in CATS" :key="c.key" :index="c.key">
            <div>
              <div>{{ c.name }}</div>
              <div style="font-size: 11px; color: var(--ink-soft)">{{ c.hint }}</div>
            </div>
          </el-menu-item>
        </el-menu>
      </div>

      <div>
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px">
            <b>{{ CATS.find(c => c.key === active)?.name }} ·
              <span class="muted" style="font-weight: 400">{{ scope === 'template' ? '默认模板' : '当前活动副本（可覆盖，不影响模板）' }}</span>
            </b>
            <el-button type="primary" @click="save">保存</el-button>
          </div>
          <el-input v-model="editing" type="textarea" :rows="22" style="font-family: var(--mono); font-size: 12.5px" />
        </div>

        <div class="card" style="margin-top: 16px">
          <b style="font-size: 13px">最近修改审计（§14）</b>
          <el-table :data="audits.slice(0, 8)" size="small" style="margin-top: 8px">
            <el-table-column label="时间" width="150">
              <template #default="{ row }"><span class="mono" style="font-size: 11px">{{ row.at?.slice(5, 16) }}</span></template>
            </el-table-column>
            <el-table-column prop="scope" label="范围" width="80" />
            <el-table-column prop="category" label="分类" width="90" />
            <el-table-column prop="operator" label="操作人" width="90" />
            <el-table-column prop="new" label="新值（截断）" />
          </el-table>
        </div>
      </div>
    </div>
  </div>
</template>
