<script setup>
// 配置中心（决策清单 §14）：默认模板 + 活动参数副本（可选继承）+ 修改审计
// 全部参数图形化编辑：下拉 / 填空 / 数字 / 表格增删行
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const CATS = [
  { key: 'activity', name: '活动参数' },
  { key: 'fee', name: '费用参数' },
  { key: 'val1', name: 'Val1 阈值' },
  { key: 'presets', name: '打印参数档' },
  { key: 'print', name: '打印/设备' },
  { key: 'compliance', name: '合规配置' },
  { key: 'qa', name: '站娘配置' },
]
const scope = ref('template')
const active = ref('activity')
const template = ref(null)
const campaignCfg = ref(null)
const audits = ref([])
const campaignId = ref(null)

// 当前编辑副本
const f = reactive({
  activity: { max_participants: 20, appeal_limit_per_campaign: 10, appeal_limit_per_model: 3, notice: '' },
  fee: { materials: [], filament_change_fee: 1.5, maintenance: { base: 0.6, per_gram: 0.004 },
         reprint_rate: {}, api: { deepseek_input_per_mtok: 2, deepseek_output_per_mtok: 8, tripo_per_point: 0.1 } },
  val1: { build_volume: { x: 256, y: 256, z: 256 }, wall_min_hard: 0.8, wall_min_soft: 1.2, overhang_warn: 30, overhang_hard: 55 },
  presets: [],
  print: { reprint_rate_machine: 0.5, queue_strategy: 'fifo', anomaly_requeue: true },
  compliance: { list: [], statement: '', pickup_location: '', pickup_window: '', contacts: [] },
  qa: { system_prompt: '', filter_words: [] },
})

const currentData = computed(() => scope.value === 'template' ? template.value?.data : campaignCfg.value)

async function load() {
  template.value = (await api.get('/admin/config/template')).template
  const meta = await api.get('/meta/bootstrap')
  campaignId.value = meta.campaign.id
  campaignCfg.value = (await api.get(`/admin/config/campaign/${meta.campaign.id}`)).config
  audits.value = (await api.get('/admin/config/audits')).audits
  syncForm()
}

function syncForm() {
  const d = currentData.value
  if (!d) return
  f.activity = { ...f.activity, ...(d.activity || {}) }
  f.fee = { ...f.fee, materials: [...(d.fee?.materials || [])], reprint_rate: { ...(d.fee?.reprint_rate || {}) },
            maintenance: { ...(d.fee?.maintenance || {}) }, api: { ...(d.fee?.api || {}) } }
  f.val1 = { ...f.val1, ...(d.val1 || {}), build_volume: { ...(d.val1?.build_volume || f.val1.build_volume) } }
  f.presets = JSON.parse(JSON.stringify(d.presets || []))
  f.print = { ...f.print, ...(d.print || {}) }
  f.compliance = { ...f.compliance, ...(d.compliance || {}), contacts: JSON.parse(JSON.stringify(d.compliance?.contacts || [])) }
  f.qa = { ...f.qa, ...(d.qa || {}) }
}

function switchScope(s) { scope.value = s; syncForm() }
function switchCat(k) { active.value = k }

function collect() {
  const c = f[active.value]
  // 文本区转数组
  if (active.value === 'compliance') c.list = complianceList.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (active.value === 'qa') c.filter_words = filterWords.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (active.value === 'fee') c.materials = materials.value
  if (active.value === 'presets') c.presets = presets.value
  return JSON.parse(JSON.stringify(c))
}

async function save() {
  const url = scope.value === 'template'
    ? `/admin/config/template/${active.value}`
    : `/admin/config/campaign/${campaignId.value}/${active.value}`
  await api.put(url, { data: collect() })
  ElMessage.success('已保存（改动即时生效，已记录审计）')
  load()
}

// —— 表格编辑辅助（材料 / 档位 / 联系人）——
const materials = ref([])
const presets = ref([])
const complianceList = ref('')
const filterWords = ref('')
const CONTACT_COLORS = ['#E8602C', '#2B6CB0', '#2F855A', '#9F7AEA', '#D69E2E', '#38B2AC']
watch(active, (k) => {
  if (k === 'fee') materials.value = JSON.parse(JSON.stringify(f.fee.materials || []))
  if (k === 'presets') presets.value = JSON.parse(JSON.stringify(f.presets || []))
  if (k === 'compliance') {
    complianceList.value = (f.compliance.list || []).join('\n')
  }
  if (k === 'qa') filterWords.value = (f.qa.filter_words || []).join('\n')
})
const addRow = (list) => list.push({})
const delRow = (list, i) => list.splice(i, 1)

onMounted(load)
</script>

<template>
  <div class="page">
    <h1 class="page-title">配置中心</h1>
    <p class="page-sub">默认模板（全局基线）与活动参数副本（可选继承）· 所有修改留审计 · 改动即时生效</p>

    <div style="display: grid; grid-template-columns: 220px 1fr; gap: 16px">
      <div style="display: flex; flex-direction: column; gap: 8px">
        <el-radio-group v-model="scope" style="margin-bottom: 8px" @change="switchScope">
          <el-radio-button value="template">默认模板</el-radio-button>
          <el-radio-button value="campaign">当前活动</el-radio-button>
        </el-radio-group>
        <el-menu :default-active="active" @select="switchCat">
          <el-menu-item v-for="c in CATS" :key="c.key" :index="c.key">{{ c.name }}</el-menu-item>
        </el-menu>
      </div>

      <div>
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px">
            <b>{{ CATS.find(c => c.key === active)?.name }} ·
              <span class="muted" style="font-weight: 400">{{ scope === 'template' ? '默认模板（全局基线）' : '当前活动副本（覆盖只影响本场）' }}</span>
            </b>
            <el-button type="primary" @click="save">保存</el-button>
          </div>

          <!-- ① 活动参数 -->
          <el-form v-if="active === 'activity'" label-width="180px" style="max-width: 560px">
            <el-form-item label="参与人数上限（§3.2）">
              <el-input-number v-model="f.activity.max_participants" :min="1" :max="50" />
            </el-form-item>
            <el-form-item label="每场申诉审核上限（§5.3）">
              <el-input-number v-model="f.activity.appeal_limit_per_campaign" :min="0" :max="100" />
            </el-form-item>
            <el-form-item label="单模型申诉次数上限（§5.3）">
              <el-input-number v-model="f.activity.appeal_limit_per_model" :min="0" :max="10" />
            </el-form-item>
            <el-form-item label="活动公告">
              <el-input v-model="f.activity.notice" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>

          <!-- ② 费用参数 -->
          <div v-else-if="active === 'fee'">
            <div style="font-weight: 600; margin-bottom: 6px">材料价格表（§11.1：成本价 × 重量 × 系数）</div>
            <el-table :data="materials" size="small" border>
              <el-table-column label="ID" width="80">
                <template #default="{ row }"><el-input v-model="row.id" size="small" /></template>
              </el-table-column>
              <el-table-column label="名称">
                <template #default="{ row }"><el-input v-model="row.name" size="small" /></template>
              </el-table-column>
              <el-table-column label="成本价(元/g)" width="120">
                <template #default="{ row }"><el-input-number v-model="row.price_per_g" size="small" :min="0" :step="0.01" :controls="false" /></template>
              </el-table-column>
              <el-table-column label="材料系数" width="100">
                <template #default="{ row }"><el-input-number v-model="row.coeff" size="small" :min="0.1" :step="0.05" :controls="false" /></template>
              </el-table-column>
              <el-table-column label="密度" width="90">
                <template #default="{ row }"><el-input-number v-model="row.density" size="small" :min="0.1" :step="0.01" :controls="false" /></template>
              </el-table-column>
              <el-table-column width="60">
                <template #default="{ $index }"><el-button link type="danger" @click="delRow(materials, $index)">删</el-button></template>
              </el-table-column>
            </el-table>
            <el-button size="small" style="margin-top: 8px" @click="addRow(materials)">+ 添加材料</el-button>

            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 18px">
              <el-form-item label="换料补偿（元/次）" style="margin-bottom: 0">
                <el-input-number v-model="f.fee.filament_change_fee" :min="0" :step="0.5" />
              </el-form-item>
              <el-form-item label="维护费基础（元/任务）" style="margin-bottom: 0">
                <el-input-number v-model="f.fee.maintenance.base" :min="0" :step="0.1" />
              </el-form-item>
              <el-form-item label="维护费每克（元/g）" style="margin-bottom: 0">
                <el-input-number v-model="f.fee.maintenance.per_gram" :min="0" :step="0.001" />
              </el-form-item>
            </div>

            <div style="font-weight: 600; margin: 16px 0 6px">重打计费比例（§10）</div>
            <div style="display: flex; gap: 16px; flex-wrap: wrap">
              <el-form-item v-for="k in ['PARAMETER', 'MACHINE', 'MODEL', 'MACHINE_LIMIT', 'OTHER']" :key="k" :label="k" style="margin-bottom: 0">
                <el-input-number v-model="f.fee.reprint_rate[k]" :min="0" :max="1" :step="0.1" />
              </el-form-item>
            </div>

            <div style="font-weight: 600; margin: 16px 0 6px">API 用量单价（§11.3，按实际用量计费）</div>
            <div style="display: flex; gap: 16px; flex-wrap: wrap">
              <el-form-item label="DeepSeek 输入(元/百万tok)" style="margin-bottom: 0">
                <el-input-number v-model="f.fee.api.deepseek_input_per_mtok" :min="0" :step="0.5" />
              </el-form-item>
              <el-form-item label="DeepSeek 输出(元/百万tok)" style="margin-bottom: 0">
                <el-input-number v-model="f.fee.api.deepseek_output_per_mtok" :min="0" :step="0.5" />
              </el-form-item>
              <el-form-item label="Tripo(元/点)" style="margin-bottom: 0">
                <el-input-number v-model="f.fee.api.tripo_per_point" :min="0" :step="0.05" />
              </el-form-item>
            </div>
          </div>

          <!-- ③ Val1 阈值 -->
          <el-form v-else-if="active === 'val1'" label-width="200px" style="max-width: 520px">
            <el-form-item label="设备打印范围 X（mm）">
              <el-input-number v-model="f.val1.build_volume.x" :min="10" :max="1000" />
            </el-form-item>
            <el-form-item label="设备打印范围 Y（mm）">
              <el-input-number v-model="f.val1.build_volume.y" :min="10" :max="1000" />
            </el-form-item>
            <el-form-item label="设备打印范围 Z（mm）">
              <el-input-number v-model="f.val1.build_volume.z" :min="10" :max="1000" />
            </el-form-item>
            <el-form-item label="壁厚硬下限（mm，低于→不通过）">
              <el-input-number v-model="f.val1.wall_min_hard" :min="0.1" :max="5" :step="0.1" />
            </el-form-item>
            <el-form-item label="壁厚警告线（mm）">
              <el-input-number v-model="f.val1.wall_min_soft" :min="0.1" :max="5" :step="0.1" />
            </el-form-item>
            <el-form-item label="悬垂警告占比（%）">
              <el-input-number v-model="f.val1.overhang_warn" :min="0" :max="100" />
            </el-form-item>
            <el-form-item label="悬垂不通过占比（%）">
              <el-input-number v-model="f.val1.overhang_hard" :min="0" :max="100" />
            </el-form-item>
          </el-form>

          <!-- ④ 打印参数档 -->
          <div v-else-if="active === 'presets'">
            <div style="font-weight: 600; margin-bottom: 6px">标准档位（参考 OrcaSlicer 标准配置，§4.2）</div>
            <el-table :data="presets" size="small" border>
              <el-table-column label="ID" width="90">
                <template #default="{ row }"><el-input v-model="row.id" size="small" /></template>
              </el-table-column>
              <el-table-column label="名称" width="110">
                <template #default="{ row }"><el-input v-model="row.name" size="small" /></template>
              </el-table-column>
              <el-table-column label="层高(mm)" width="100">
                <template #default="{ row }"><el-input-number v-model="row.layer_height" size="small" :min="0.04" :max="0.5" :step="0.04" :controls="false" /></template>
              </el-table-column>
              <el-table-column label="填充(%)" width="90">
                <template #default="{ row }"><el-input-number v-model="row.infill" size="small" :min="0" :max="100" :controls="false" /></template>
              </el-table-column>
              <el-table-column label="速度" width="90">
                <template #default="{ row }"><el-input-number v-model="row.speed" size="small" :min="10" :max="300" :controls="false" /></template>
              </el-table-column>
              <el-table-column label="支撑" width="100">
                <template #default="{ row }">
                  <el-select v-model="row.supports" size="small">
                    <el-option value="auto" label="自动" /><el-option value="none" label="无" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="说明">
                <template #default="{ row }"><el-input v-model="row.note" size="small" /></template>
              </el-table-column>
              <el-table-column width="60">
                <template #default="{ $index }"><el-button link type="danger" @click="delRow(presets, $index)">删</el-button></template>
              </el-table-column>
            </el-table>
            <el-button size="small" style="margin-top: 8px" @click="addRow(presets)">+ 添加档位</el-button>
          </div>

          <!-- ⑤ 打印/设备 -->
          <el-form v-else-if="active === 'print'" label-width="220px" style="max-width: 520px">
            <el-form-item label="设备问题重打比例（§10.2）">
              <el-input-number v-model="f.print.reprint_rate_machine" :min="0" :max="1" :step="0.1" />
            </el-form-item>
            <el-form-item label="队列调度策略（§8.2）">
              <el-select v-model="f.print.queue_strategy" style="width: 220px">
                <el-option value="fifo" label="先来先服务（FIFO）" />
                <el-option value="priority" label="按优先级" />
              </el-select>
            </el-form-item>
            <el-form-item label="异常自动重新排队（§16.4）">
              <el-switch v-model="f.print.anomaly_requeue" />
            </el-form-item>
          </el-form>

          <!-- ⑥ 合规配置 -->
          <div v-else-if="active === 'compliance'">
            <el-form label-width="140px" style="max-width: 640px">
              <el-form-item label="平台声明">
                <el-input v-model="f.compliance.statement" type="textarea" :rows="2" />
              </el-form-item>
              <el-form-item label="取件地点（§16.1）">
                <el-input v-model="f.compliance.pickup_location" />
              </el-form-item>
              <el-form-item label="取件时间窗口">
                <el-input v-model="f.compliance.pickup_window" />
              </el-form-item>
            </el-form>
            <div style="font-weight: 600; margin: 8px 0 6px">禁止打印清单（§7.4，每行一条）</div>
            <el-input v-model="complianceList" type="textarea" :rows="4" />
            <div style="font-weight: 600; margin: 16px 0 6px">线下负责人（§16.2，每年级 2 人）</div>
            <div v-for="(g, i) in f.compliance.contacts" :key="i" style="display: flex; gap: 8px; margin-bottom: 8px; align-items: center">
              <el-input v-model="g.grade" placeholder="年级" style="width: 120px" />
              <el-input v-model="g.members" placeholder="成员，用顿号分隔（如 李同学 138****1024、王同学 …）" />
              <el-button link type="danger" @click="delRow(f.compliance.contacts, i)">删</el-button>
            </div>
            <el-button size="small" @click="f.compliance.contacts.push({ grade: '', members: '' })">+ 添加年级</el-button>
          </div>

          <!-- ⑦ 站娘配置 -->
          <div v-else-if="active === 'qa'">
            <el-form label-width="140px" style="max-width: 720px">
              <el-form-item label="System Prompt">
                <el-input v-model="f.qa.system_prompt" type="textarea" :rows="6"
                          placeholder="支持 {step} 当前步骤、{statement} 合规声明 变量；自监督指令与过滤拦截由系统自动追加" />
              </el-form-item>
            </el-form>
            <div style="font-weight: 600; margin: 8px 0 6px">过滤词（输入/输出双向检测，每行一个）</div>
            <el-input v-model="filterWords" type="textarea" :rows="3" />
          </div>
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
