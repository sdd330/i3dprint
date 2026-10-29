<script setup>
// 活动（场次）管理（§12.1 / §14）
// 2026-10 新增：活动列表 / 新建（继承参数）/ 编辑基本信息 / 切换当前活动 / 生命周期 / 账单
// 「当前活动」决定学生端与负责人端看到的场次（指针存 AppSetting.current_campaign_id）
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { useAppStore } from '@/stores'

const router = useRouter()
const app = useAppStore()
const rows = ref([])
const loading = ref(true)
const billingVisible = computed(() => app.billingVisible)

const STATUS_FLOW = ['待开放', '开放中', '收尾中', '已归档']
const STATUS_TAG = { 待开放: 'info', 开放中: 'success', 收尾中: 'warning', 已归档: 'info' }

async function load() {
  loading.value = true
  try {
    rows.value = (await api.get('/admin/campaigns')).campaigns
    await app.loadMeta()
  } finally {
    loading.value = false
  }
}

function nextStatus(s) {
  const i = STATUS_FLOW.indexOf(s)
  return i >= 0 && i < STATUS_FLOW.length - 1 ? STATUS_FLOW[i + 1] : null
}
const NEXT_LABEL = { 开放中: '开放（开始接单）', 收尾中: '收尾（停止接单）', 已归档: '归档（生成账单）' }

async function transition(row, to) {
  await ElMessageBox.confirm(`确认将「${row.name}」从「${row.status}」切换到「${to}」？`, '活动生命周期')
  await api.post(`/admin/campaign/transition?campaign_id=${row.id}`, { to })
  ElMessage.success(`「${row.name}」→ ${to}`)
  load()
}

async function activate(row) {
  if (row.is_current) return
  await ElMessageBox.confirm(`将「${row.name}」设为当前活动？学生端与负责人端都会切到这一场。`, '切换当前活动')
  await api.post(`/admin/campaigns/${row.id}/activate`, {})
  ElMessage.success('已切换当前活动')
  load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除活动「${row.name}」？（仅允许删除没有需求的活动）`, '删除活动')
  try {
    await api.del(`/admin/campaigns/${row.id}`)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

// —— 新建活动 ——
const createVisible = ref(false)
const creating = ref(false)
const createForm = reactive({
  name: '', open_at: '', close_at: '', max_participants: 20, password: '', inherit: 'template', inherit_id: null,
})
function openCreate() {
  createForm.name = ''
  createForm.open_at = ''
  createForm.close_at = ''
  createForm.max_participants = 20
  createForm.password = ''
  createForm.inherit = 'template'
  createForm.inherit_id = rows.value.find(r => r.is_current)?.id || null
  createVisible.value = true
}
async function submitCreate() {
  if (!createForm.name.trim()) return ElMessage.warning('请填写活动名称')
  creating.value = true
  try {
    const d = await api.post('/admin/campaigns', { ...createForm })
    ElMessage.success(`已创建「${d.campaign.name}」并设为当前活动`)
    createVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    creating.value = false
  }
}

// —— 编辑活动 ——
const editVisible = ref(false)
const editing = ref(null)
const editForm = reactive({ name: '', password: '', open_at: '', close_at: '', max_participants: 20 })
function openEdit(row) {
  editing.value = row
  Object.assign(editForm, {
    name: row.name, password: row.password, open_at: row.open_at || '',
    close_at: row.close_at || '', max_participants: row.max_participants || 20,
  })
  editVisible.value = true
}
async function submitEdit() {
  await api.put(`/admin/campaigns/${editing.value.id}`, { ...editForm })
  ElMessage.success('已保存')
  editVisible.value = false
  load()
}

// —— 账单 ——
const bill = ref(null)
const billVisible = ref(false)
async function showBill(row) {
  bill.value = (await api.get(`/admin/campaign/bill?campaign_id=${row.id}`)).bill
  billVisible.value = true
}

function goConfig(row) {
  router.push('/admin/config')
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div style="display: flex; justify-content: space-between; align-items: end; flex-wrap: wrap; gap: 12px">
      <div>
        <h1 class="page-title">活动管理</h1>
        <p class="page-sub">
          每场活动是一个独立场次（订单不跨场）· 参数按场复制、可继承上一场 · 「当前活动」决定学生端与负责人端看到的场次
        </p>
      </div>
      <div style="display: flex; gap: 8px">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">+ 新建活动</el-button>
      </div>
    </div>

    <div v-loading="loading" style="display: flex; flex-direction: column; gap: 12px; margin-top: 16px">
      <div v-for="row in rows" :key="row.id" class="card" style="margin: 0; padding: 14px 16px"
           :style="{ borderColor: row.is_current ? 'var(--accent)' : 'var(--line)', borderWidth: row.is_current ? '2px' : '1px' }">
        <div style="display: flex; justify-content: space-between; align-items: start; gap: 12px; flex-wrap: wrap">
          <div>
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
              <b style="font-size: 15.5px">{{ row.name }}</b>
              <el-tag size="small" :type="STATUS_TAG[row.status] || 'info'">{{ row.status }}</el-tag>
              <el-tag v-if="row.is_current" size="small" type="success" effect="dark">当前活动</el-tag>
              <span class="muted mono" style="font-size: 11.5px">#{{ row.id }}</span>
            </div>
            <div class="muted" style="font-size: 12.5px; margin-top: 6px; display: flex; gap: 14px; flex-wrap: wrap">
              <span>开放 {{ row.open_at || '—' }}</span>
              <span>收尾 {{ row.close_at || '—' }}</span>
              <span>人数上限 {{ row.max_participants }}</span>
              <span>取件密码 <b class="mono">{{ row.password }}</b></span>
            </div>
            <div class="muted" style="font-size: 12.5px; margin-top: 4px; display: flex; gap: 14px; flex-wrap: wrap">
              <span>需求 {{ row.orders_active }} 进行中 / {{ row.orders_total }} 总计</span>
              <span v-if="Object.keys(row.config_sources || {}).length">
                参数来源：{{ Object.values(row.config_sources).includes('custom') ? '含本场自定义' : '继承' }}
              </span>
              <span v-if="row.archived_at">归档于 {{ row.archived_at?.slice(0, 16) }}</span>
            </div>
          </div>

          <div style="display: flex; gap: 6px; flex-wrap: wrap; align-items: center">
            <el-button v-if="!row.is_current" size="small" type="primary" plain @click="activate(row)">设为当前</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" @click="goConfig(row)">参数配置</el-button>
            <el-button v-if="nextStatus(row.status)" size="small" type="warning"
                       @click="transition(row, nextStatus(row.status))">
              {{ NEXT_LABEL[nextStatus(row.status)] }}
            </el-button>
            <el-button v-if="row.status === '已归档' || row.status === '收尾中'" size="small"
                       @click="transition(row, '开放中')">重新开放</el-button>
            <el-button v-if="row.status === '已归档' && billingVisible" size="small" @click="showBill(row)">账单</el-button>
            <el-button v-if="!row.orders_total" size="small" type="danger" plain @click="remove(row)">删除</el-button>
          </div>
        </div>

        <!-- 生命周期进度 -->
        <el-steps :active="Math.max(0, STATUS_FLOW.indexOf(row.status))" align-center style="margin-top: 12px; max-width: 520px">
          <el-step v-for="s in STATUS_FLOW" :key="s" :title="s" />
        </el-steps>
      </div>
      <el-empty v-if="!rows.length && !loading" description="还没有活动，点右上角新建" :image-size="70" />
    </div>

    <!-- 新建活动 -->
    <el-dialog v-model="createVisible" title="新建活动" width="560px">
      <el-form label-position="top">
        <el-form-item label="活动名称">
          <el-input v-model="createForm.name" placeholder="如：2026 秋季第 2 场 · 3D 打印体验活动" />
        </el-form-item>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
          <el-form-item label="开放时间">
            <el-input v-model="createForm.open_at" placeholder="2026-11-01T09:00:00" />
          </el-form-item>
          <el-form-item label="收尾时间">
            <el-input v-model="createForm.close_at" placeholder="2026-11-02T18:00:00" />
          </el-form-item>
          <el-form-item label="人数上限">
            <el-input-number v-model="createForm.max_participants" :min="1" :max="200" style="width: 100%" />
          </el-form-item>
          <el-form-item label="取件密码（留空自动生成）">
            <el-input v-model="createForm.password" placeholder="E3DP-AUTUMN" />
          </el-form-item>
        </div>
        <el-form-item label="参数继承（§14 可选继承）">
          <el-radio-group v-model="createForm.inherit">
            <el-radio value="template">继承默认模板</el-radio>
            <el-radio value="previous">继承指定场次</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="createForm.inherit === 'previous'" label="继承自哪一场">
          <el-select v-model="createForm.inherit_id" style="width: 100%">
            <el-option v-for="r in rows" :key="r.id" :value="r.id" :label="`${r.name}（${r.status}）`" />
          </el-select>
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon
                  title="新活动会复制一份参数副本并自动设为「当前活动」"
                  description="费用/阈值/材料颜色/强度档/打印机清单都在配置中心按场维护，改动只影响该场。" />
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑活动 -->
    <el-dialog v-model="editVisible" :title="`编辑活动 · ${editing?.name}`" width="540px">
      <el-form label-position="top">
        <el-form-item label="活动名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
          <el-form-item label="开放时间">
            <el-input v-model="editForm.open_at" />
          </el-form-item>
          <el-form-item label="收尾时间">
            <el-input v-model="editForm.close_at" />
          </el-form-item>
          <el-form-item label="人数上限">
            <el-input-number v-model="editForm.max_participants" :min="1" :max="200" style="width: 100%" />
          </el-form-item>
          <el-form-item label="取件密码">
            <el-input v-model="editForm.password" />
          </el-form-item>
        </div>
        <div class="muted" style="font-size: 12px">
          活动状态用「开放 / 收尾 / 归档」按钮流转（待开放 → 开放中 → 收尾中 → 已归档），不可直接编辑。
        </div>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 账单 -->
    <el-dialog v-model="billVisible" title="活动账单（§12.4）" width="640px">
      <template v-if="bill">
        <el-table :data="bill.rows" size="small">
          <el-table-column prop="order_id" label="需求" width="70">
            <template #default="{ row }">O{{ row.order_id }}</template>
          </el-table-column>
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="user" label="用户" width="90" />
          <el-table-column prop="filament" label="耗材" width="80" />
          <el-table-column prop="maintenance" label="维护" width="80" />
          <el-table-column prop="total" label="合计" width="90">
            <template #default="{ row }"><span class="amount">¥{{ row.total.toFixed(2) }}</span></template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!bill.rows.length" description="暂无已结需求" :image-size="60" />
      </template>
    </el-dialog>
  </div>
</template>
