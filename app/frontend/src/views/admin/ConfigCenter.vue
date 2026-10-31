<script setup>
// 配置中心（决策清单 §14）：默认模板 + 活动参数副本（可选继承）+ 修改审计
// 全部参数图形化编辑：下拉 / 填空 / 数字 / 表格增删行
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { useAppStore } from '@/stores'

const app = useAppStore()
const billingVisible = computed(() => app.billingVisible)

const CATS_BASE = [
  { key: 'activity', name: '活动参数' },
  { key: 'fee', name: '材料与耗材' },
  { key: 'val1', name: 'Val1 阈值' },
  { key: 'strength_tiers', name: '强度档（打印需求）' },
  { key: 'presets', name: '旧参数档（暂缓）' },
  { key: 'print', name: '打印/设备' },
  { key: 'compliance', name: '合规配置' },
  { key: 'qa', name: '站娘配置' },
]
// 计费隐藏时把「材料与耗材」明确成材料配置（价格/系数/维护费等不展示）
const CATS = computed(() => CATS_BASE.map(c =>
  c.key === 'fee' && !billingVisible.value ? { ...c, name: '材料与耗材' } : c))
const scope = ref('campaign')   // 默认编辑「当前活动」副本，改动立刻对学生端生效
const active = ref('activity')
const template = ref(null)
const campaignCfg = ref(null)
const audits = ref([])
const campaignId = ref(null)

// 当前编辑副本
const f = reactive({
  activity: { max_participants: 20, appeal_limit_per_campaign: 10, appeal_limit_per_model: 3, notice: '' },
  fee: { materials: [], filament_change_fee: 1.5, maintenance: { base: 0.6, per_gram: 0.004 },
         reprint_rate: {}, api: { llm_input_per_mtok: 2, llm_output_per_mtok: 8, tripo_per_point: 0.1 } },
  val1: { build_volume: { x: 256, y: 256, z: 256 }, wall_min_hard: 0.8, wall_min_soft: 1.2, overhang_warn: 30, overhang_hard: 55 },
  presets: [],
  strength_tiers: [],
  print: { reprint_rate_machine: 1.0, queue_strategy: 'fifo', anomaly_requeue: true, printers: [] },
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
  f.strength_tiers = JSON.parse(JSON.stringify(d.strength_tiers || []))
  f.print = { ...f.print, ...(d.print || {}), printers: JSON.parse(JSON.stringify(d.print?.printers || [])) }
  f.compliance = { ...f.compliance, ...(d.compliance || {}), contacts: JSON.parse(JSON.stringify(d.compliance?.contacts || [])) }
  // 线下负责人：后端存的是成员数组，这里转成一行文本编辑（顿号分隔）
  f.compliance.contacts = (f.compliance.contacts || []).map(c => ({
    grade: c.grade || '',
    members: Array.isArray(c.members) ? c.members.join('、') : (c.members || ''),
  }))
  f.qa = { ...f.qa, ...(d.qa || {}) }
}

function switchScope(s) { scope.value = s; syncForm() }
function switchCat(k) { active.value = k }

function collect() {
  const c = f[active.value]
  // 文本区转数组
  if (active.value === 'compliance') {
    c.list = complianceList.value.split('\n').map(s => s.trim()).filter(Boolean)
    // 线下负责人：文本 → 成员数组（顿号/逗号/分号/斜杠分隔）
    c.contacts = (c.contacts || []).map(x => ({
      grade: (x.grade || '').trim(),
      members: String(x.members || '').split(/[、,，;；/|]+/).map(t => t.trim()).filter(Boolean),
    })).filter(x => x.grade || x.members.length)
  }
  if (active.value === 'qa') c.filter_words = filterWords.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (active.value === 'fee') {
    c.materials = materials.value.map(({ _colorsText, ...m }) => ({
      ...m,
      colors: parseColors(_colorsText).map(x => ({ name: x.name, hex: x.hex })),
    }))
  }
  if (active.value === 'presets') c.presets = presets.value
  if (active.value === 'strength_tiers') c.strength_tiers = strengthTiers.value
  if (active.value === 'print') c.printers = printers.value
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
const strengthTiers = ref([])
const printers = ref([])
const complianceList = ref('')
const filterWords = ref('')
const CONTACT_COLORS = ['#E8602C', '#2B6CB0', '#2F855A', '#9F7AEA', '#D69E2E', '#38B2AC']
watch(active, (k) => {
  if (k === 'fee') {
    materials.value = JSON.parse(JSON.stringify(f.fee.materials || []))
    // colors → 编辑用文本（名称:HEX，逗号分隔）
    for (const m of materials.value) {
      m._colorsText = (m.colors || [])
        .map(c => typeof c === 'string' ? c : (c?.name ? `${c.name}:${c.hex}` : c?.hex))
        .filter(Boolean).join(', ')
    }
  }
  if (k === 'presets') presets.value = JSON.parse(JSON.stringify(f.presets || []))
  if (k === 'strength_tiers') strengthTiers.value = JSON.parse(JSON.stringify(f.strength_tiers || []))
  if (k === 'print') printers.value = JSON.parse(JSON.stringify(f.print.printers || []))
  if (k === 'compliance') {
    complianceList.value = (f.compliance.list || []).join('\n')
  }
  if (k === 'qa') filterWords.value = (f.qa.filter_words || []).join('\n')
})
// 「白:#F5F5F0, 黑:#23262B」→ [{name, hex}]；也接受纯 HEX（名称用 HEX 顶替）
function parseColors(text) {
  if (!text) return []
  return String(text)
    .split(/[,，;；\n]/)
    .map(t => t.trim())
    .filter(Boolean)
    .map(t => {
      const m = t.match(/^(.+?)\s*[:：]\s*(#[0-9a-fA-F]{3,8})$/)
      if (m) return { name: m[1].trim(), hex: m[2].trim() }
      return { name: t, hex: t }
    })
    .filter(c => /^#[0-9a-fA-F]{3,8}$/.test(c.hex))
}

const addRow = (list) => list.push({})
// 新增打印机：编号按现有数量顺延，默认启用
function addPrinter() {
  const n = printers.value.length + 1
  printers.value.push({ id: `x1c-0${n}`, name: `X1C-0${n}`, model: 'Bambu Lab X1-Carbon', enabled: true })
}
const delRow = (list, i) => list.splice(i, 1)

onMounted(async () => {
  if (!app.meta) await app.loadMeta().catch(() => {})
  load()
})
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
              <span class="muted" style="font-weight: 400">{{ scope === 'template' ? '默认模板（全局基线，只影响新建活动）' : '当前活动副本（改动立刻对学生端生效）' }}</span>
            </b>
            <el-button type="primary" @click="save">保存</el-button>
          </div>

          <el-alert v-if="scope === 'template'" type="warning" :closable="false" show-icon style="margin-bottom: 12px"
                    title="你正在编辑「默认模板」——它只在**新建活动**时被复制"
                    description="要让学生端立刻看到改动，请把右上角切到「当前活动」。当前活动已有自己的参数副本，模板改动不会自动同步过去。" />

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

          <!-- ② 材料与耗材（计费部分在 billing 隐藏时不展示） -->
          <template v-else-if="active === 'fee'">
            <el-alert type="info" :closable="false" show-icon style="margin-bottom: 10px"
                      :title="billingVisible ? '材料与计费' : '材料配置（计费部分已暂时隐藏）'"
                      :description="billingVisible
                        ? '材料价格/系数、换料补偿、维护费、重打比例、API 单价都在这里维护。'
                        : '这里维护材料的名称、密度和每种材料的有货颜色（打印需求页直接读）。价格、系数、换料补偿、维护费、重打比例、API 单价暂不显示。'" />
            <div style="font-weight: 600; margin-bottom: 6px">材料清单（名称 / 密度 / 有货颜色）</div>
            <el-table :data="materials" size="small" border>
              <el-table-column label="ID" width="80">
                <template #default="{ row }"><el-input v-model="row.id" size="small" /></template>
              </el-table-column>
              <el-table-column label="名称">
                <template #default="{ row }"><el-input v-model="row.name" size="small" /></template>
              </el-table-column>
              <el-table-column v-if="billingVisible" label="成本价(元/g)" width="120">
                <template #default="{ row }"><el-input-number v-model="row.price_per_g" size="small" :min="0" :step="0.01" :controls="false" /></template>
              </el-table-column>
              <el-table-column v-if="billingVisible" label="材料系数" width="100">
                <template #default="{ row }"><el-input-number v-model="row.coeff" size="small" :min="0.1" :step="0.05" :controls="false" /></template>
              </el-table-column>
              <el-table-column label="密度" width="90">
                <template #default="{ row }"><el-input-number v-model="row.density" size="small" :min="0.1" :step="0.01" :controls="false" /></template>
              </el-table-column>
              <el-table-column label="有货颜色（名称:HEX，逗号分隔）" min-width="260">
                <template #default="{ row }">
                  <el-input v-model="row._colorsText" size="small"
                            placeholder="白:#F5F5F0, 黑:#23262B, 橙:#E8602C" />
                  <div style="display: flex; gap: 4px; margin-top: 4px; flex-wrap: wrap">
                    <span v-for="c in parseColors(row._colorsText)" :key="c.hex"
                          :style="{ display: 'inline-block', width: 14, height: 14, borderRadius: 3, background: c.hex, border: '1px solid var(--line)' }"
                          :title="`${c.name} ${c.hex}`" />
                  </div>
                </template>
              </el-table-column>
              <el-table-column width="60">
                <template #default="{ $index }"><el-button link type="danger" @click="delRow(materials, $index)">删</el-button></template>
              </el-table-column>
            </el-table>
            <el-button size="small" style="margin-top: 8px" @click="addRow(materials)">+ 添加材料</el-button>

            <div v-if="billingVisible" style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 18px">
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

            <div v-if="billingVisible" style="font-weight: 600; margin: 16px 0 6px">重打计费比例（§10）</div>
            <div v-if="billingVisible" style="display: flex; gap: 16px; flex-wrap: wrap">
              <el-form-item v-for="k in ['PARAMETER', 'MACHINE', 'MODEL', 'MACHINE_LIMIT', 'OTHER']" :key="k" :label="k" style="margin-bottom: 0">
                <el-input-number v-model="f.fee.reprint_rate[k]" :min="0" :max="1" :step="0.1" />
              </el-form-item>
            </div>

            <div v-if="billingVisible" style="font-weight: 600; margin: 16px 0 6px">API 用量单价（§11.3，按实际用量计费）</div>
            <div v-if="billingVisible" style="display: flex; gap: 16px; flex-wrap: wrap">
              <el-form-item label="对话模型 输入(元/百万tok)" style="margin-bottom: 0">
                <el-input-number v-model="f.fee.api.llm_input_per_mtok" :min="0" :step="0.5" />
              </el-form-item>
              <el-form-item label="对话模型 输出(元/百万tok)" style="margin-bottom: 0">
                <el-input-number v-model="f.fee.api.llm_output_per_mtok" :min="0" :step="0.5" />
              </el-form-item>
              <el-form-item label="Tripo(元/点)" style="margin-bottom: 0">
                <el-input-number v-model="f.fee.api.tripo_per_point" :min="0" :step="0.05" />
              </el-form-item>
            </div>
          </template>

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

          <!-- ④ 强度档（打印需求页展示给用户，直接决定工艺参数） -->
          <div v-else-if="active === 'strength_tiers'">
            <el-alert type="info" :closable="false" show-icon style="margin-bottom: 10px"
                      title="这一组就是「打印需求」页里学生看到的强度选项"
                      description="学生选强度 → 系统按此处的壁厚圈数 / 填充率 / 层高 / 顶底实心层 / 填充图案生成工艺参数，再交给执行打印的人。可增删档位、改名称与图标。" />
            <el-table :data="strengthTiers" size="small" border>
              <el-table-column label="ID" width="90">
                <template #default="{ row }"><el-input v-model="row.id" size="small" placeholder="light" /></template>
              </el-table-column>
              <el-table-column label="名称" width="100">
                <template #default="{ row }"><el-input v-model="row.name" size="small" placeholder="轻量" /></template>
              </el-table-column>
              <el-table-column label="图标" width="70">
                <template #default="{ row }"><el-input v-model="row.icon" size="small" /></template>
              </el-table-column>
              <el-table-column label="说明">
                <template #default="{ row }"><el-input v-model="row.desc" size="small" /></template>
              </el-table-column>
              <el-table-column label="层高(mm)" width="100">
                <template #default="{ row }"><el-input-number v-model="row.layer_height" size="small" :min="0.04" :max="0.5" :step="0.04" :controls="false" /></template>
              </el-table-column>
              <el-table-column label="壁厚圈数" width="95">
                <template #default="{ row }"><el-input-number v-model="row.wall_loops" size="small" :min="1" :max="8" :controls="false" /></template>
              </el-table-column>
              <el-table-column label="填充(%)" width="90">
                <template #default="{ row }"><el-input-number v-model="row.infill_density" size="small" :min="0" :max="100" :step="5" :controls="false" /></template>
              </el-table-column>
              <el-table-column label="顶/底实心层" width="120">
                <template #default="{ row }">
                  <div style="display: flex; gap: 4px">
                    <el-input-number v-model="row.top_shell_layers" size="small" :min="0" :max="12" :controls="false" style="width: 52px" />
                    <el-input-number v-model="row.bottom_shell_layers" size="small" :min="0" :max="12" :controls="false" style="width: 52px" />
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="填充图案" width="120">
                <template #default="{ row }">
                  <el-select v-model="row.infill_pattern" size="small">
                    <el-option v-for="p in ['grid', 'gyroid', 'cubic', 'lines', 'triangles', 'adaptive cubic']" :key="p" :value="p" :label="p" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column width="60">
                <template #default="{ $index }"><el-button link type="danger" @click="delRow(strengthTiers, $index)">删</el-button></template>
              </el-table-column>
            </el-table>
            <el-button size="small" style="margin-top: 8px"
                       @click="addRow(strengthTiers)">+ 添加强度档</el-button>
            <div class="muted" style="font-size: 12px; margin-top: 6px">
              提示：至少保留一个档位；学生端「打印需求」页直接读取这里的配置（保存后即时生效）。
            </div>
          </div>

          <!-- ④b 旧打印参数档（在线切片暂缓，当前不参与主链） -->
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

          <template v-if="active === 'print'">
            <div style="font-weight: 600; margin: 18px 0 6px">打印机清单（决定可同时开机数 / 排产）</div>
            <el-table :data="printers" size="small" border style="max-width: 780px">
              <el-table-column label="编号 (id)" width="140">
                <template #default="{ row }"><el-input v-model="row.id" size="small" placeholder="x1c-01" /></template>
              </el-table-column>
              <el-table-column label="名称" width="150">
                <template #default="{ row }"><el-input v-model="row.name" size="small" placeholder="X1C-01" /></template>
              </el-table-column>
              <el-table-column label="型号">
                <template #default="{ row }"><el-input v-model="row.model" size="small" placeholder="Bambu Lab X1-Carbon" /></template>
              </el-table-column>
              <el-table-column label="启用" width="80">
                <template #default="{ row }"><el-switch v-model="row.enabled" /></template>
              </el-table-column>
              <el-table-column width="60">
                <template #default="{ $index }"><el-button link type="danger" @click="delRow(printers, $index)">删</el-button></template>
              </el-table-column>
            </el-table>
            <el-button size="small" style="margin-top: 8px" @click="addPrinter">+ 添加打印机</el-button>
            <div class="muted" style="font-size: 12px; margin-top: 6px">
              编号设得稳定一点（如 x1c-01），已分配的历史任务按编号关联；停用某台不影响历史记录。
              打印范围统一取上面「Val1 阈值」里的设备打印范围。
            </div>
          </template>

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
