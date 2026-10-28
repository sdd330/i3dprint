<script setup>
// 打印需求配置（§4.2 调整版）：Val1 通过 / 人工放行后填写「材料 + 强度 + 进阶参数」
// 2026-10：**不做在线切片**，提交即生成「打印清单」交给执行打印的负责人；
//          收费信息暂时隐去（flow.billing_visible=false），页面不出现单价与费用。
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { useAppStore } from '@/stores'
import AdvancedParamsForm from '@/components/AdvancedParamsForm.vue'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const orderId = Number(route.params.id)
const order = ref(null)
const loading = ref(true)
const submitting = ref(false)
const result = ref(null)        // 提交后的清单结果
const resultVisible = ref(false)

const PALETTE = ['#E8602C', '#2B6CB0', '#2F855A', '#D69E2E', '#38B2AC', '#9F7AEA', '#F687B3', '#CBD5E0']

// 进阶参数默认值 = X1C 标准档基准（字段名同 OrcaSlicer）
const DEFAULTS = {
  layer_height: 0.2, initial_layer_print_height: 0.2, wall_loops: 2,
  top_shell_layers: 4, bottom_shell_layers: 3, infill_density: 20, infill_pattern: 'grid',
  outer_wall_speed: 200, inner_wall_speed: 300, sparse_infill_speed: 270, travel_speed: 500,
  initial_layer_speed: 50, nozzle_temperature: 220, initial_layer_print_temperature: 220,
  bed_temperature: 65, initial_layer_bed_temperature: 65,
  enable_support: 'auto', support_type: 'normal(auto)', support_threshold_angle: 30,
  retraction_length: 0.8, retraction_speed: 30, z_hop: 0.4, max_volumetric_speed: 21,
}

const form = reactive({
  material: 'pla',
  color: '#E8602C',
  strength: 'standard',
  selfFilament: false,
  note: '',
})
const advancedOn = ref(false)
const advanced = reactive({ ...DEFAULTS })

const materials = computed(() => app.materials)
const tiers = computed(() => app.strengthTiers)
const tier = computed(() => tiers.value.find(t => t.id === form.strength))
const material = computed(() => materials.value.find(m => m.id === form.material))
const billingVisible = computed(() => app.billingVisible)
const val1 = computed(() => order.value?.val1)
const bbox = computed(() => order.value?.geometry?.bbox || val1.value?.stats?.bbox)
const volume = computed(() => val1.value?.stats?.volume_cm3)

watch(() => form.material, (m) => {
  const mat = materials.value.find(x => x.id === m)
  if (mat?.colors?.length) form.color = mat.colors[0]
})

// 切换强度档时把核心三项同步到进阶参数（用户在进阶里仍可覆盖）
watch(() => form.strength, (id) => {
  const t = tiers.value.find(x => x.id === id)
  if (!t) return
  advanced.layer_height = t.layer_height
  advanced.wall_loops = t.wall_loops
  advanced.infill_density = t.infill_density
  advanced.top_shell_layers = t.top_shell_layers
  advanced.bottom_shell_layers = t.bottom_shell_layers
  advanced.infill_pattern = t.infill_pattern
})

async function load() {
  loading.value = true
  try {
    await app.loadMeta()
    order.value = (await api.get(`/orders/${orderId}`)).order
    if (order.value.material_id) form.material = order.value.material_id
    if (order.value.color) form.color = order.value.color
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function submit() {
  submitting.value = true
  try {
    const d = await api.post(`/orders/${orderId}/print-requirement`, {
      material_id: form.material,
      color: form.color,
      strength: form.strength,
      advanced: advancedOn.value ? { ...advanced } : null,
      self_filament: form.selfFilament,
      operator_note: form.note,
    })
    order.value = d.order
    result.value = d
    resultVisible.value = true
    ElMessage.success('打印需求已提交，已生成打印清单')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

function goOrder() { router.push(`/orders/${orderId}`) }
function goWorkspace() { router.push(`/create/${orderId}/workspace`) }

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <h1 class="page-title">打印需求 · O{{ orderId }}</h1>
    <p class="page-sub">
      选择材料、强度和进阶参数。提交后生成一张打印清单，由负责人照清单执行打印 ——
      <b>当前版本不做在线切片</b>。
    </p>

    <div style="display: grid; grid-template-columns: 1.55fr 1fr; gap: 20px; align-items: start">
      <!-- 左：表单 -->
      <div style="display: flex; flex-direction: column; gap: 16px">
        <!-- 材料 -->
        <div class="card">
          <h3 style="margin: 0 0 12px">① 材料</h3>
          <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px">
            <div v-for="m in materials" :key="m.id"
                 @click="form.material = m.id"
                 :style="{
                   border: `2px solid ${form.material === m.id ? 'var(--accent)' : 'var(--line)'}`,
                   background: form.material === m.id ? 'var(--accent-soft)' : 'var(--card)',
                   borderRadius: 10, padding: '10px 12px', cursor: 'pointer', transition: 'all .15s',
                 }">
              <div style="font-weight: 700; font-size: 13.5px">{{ m.name }}</div>
              <div class="muted" style="font-size: 12px; margin-top: 2px">
                密度 {{ m.density || '—' }} g/cm³
                <span v-if="billingVisible"> · {{ m.price_per_g }} 元/g ×{{ m.coeff }}</span>
              </div>
              <div class="muted" style="font-size: 11.5px; margin-top: 4px">
                {{ { pla: '最常用，摆件首选', petg: '更韧更耐温，功能件', abs: '强度高，易翘边', tpu: '柔性材料' }[m.id] || '' }}
              </div>
            </div>
          </div>

          <div style="margin-top: 14px">
            <div class="muted" style="font-size: 12px; margin-bottom: 6px">颜色</div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap">
              <span v-for="c in PALETTE" :key="c" @click="form.color = c"
                    :style="{ display: 'inline-block', width: '28px', height: '28px', borderRadius: '8px', background: c, cursor: 'pointer',
                              border: form.color === c ? '3px solid #23262b' : '2px solid #fff',
                              boxShadow: '0 0 0 1px var(--line)' }" />
            </div>
          </div>
        </div>

        <!-- 强度 -->
        <div class="card">
          <h3 style="margin: 0 0 12px">② 强度</h3>
          <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px">
            <div v-for="t in tiers" :key="t.id" @click="form.strength = t.id"
                 :style="{
                   border: `2px solid ${form.strength === t.id ? 'var(--accent)' : 'var(--line)'}`,
                   background: form.strength === t.id ? 'var(--accent-soft)' : 'var(--card)',
                   borderRadius: 10, padding: '10px 12px', cursor: 'pointer', transition: 'all .15s',
                 }">
              <div style="font-weight: 700; font-size: 13.5px">{{ t.icon }} {{ t.name }}</div>
              <div class="muted" style="font-size: 12px; margin-top: 2px">{{ t.desc }}</div>
              <div class="mono muted" style="font-size: 11.5px; margin-top: 4px">
                壁厚 {{ t.wall_loops }} 圈 · 填充 {{ t.infill_density }}%
              </div>
            </div>
          </div>
          <div v-if="tier" class="muted" style="font-size: 12px; margin-top: 8px">
            已选「{{ tier.name }}」：层高 {{ tier.layer_height }}mm · 壁厚 {{ tier.wall_loops }} 圈 · 填充 {{ tier.infill_density }}%（{{ tier.infill_pattern }}）
          </div>
        </div>

        <!-- 进阶参数 -->
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: center">
            <h3 style="margin: 0">③ 进阶参数</h3>
            <el-switch v-model="advancedOn" active-text="手动调整" />
          </div>
          <div v-if="!advancedOn" class="muted" style="font-size: 12.5px; margin-top: 8px">
            默认按「{{ tier?.name }}」强度档参数执行（层高 / 壁厚圈数 / 顶底实心层 / 填充率与图案）。
            需要改速度、温度、支撑、回抽等细节时打开右侧开关。
          </div>
          <div v-else style="margin-top: 12px">
            <AdvancedParamsForm v-model="advanced" />
            <el-button link type="primary" @click="Object.assign(advanced, DEFAULTS)">恢复默认值</el-button>
          </div>
        </div>

        <!-- 自备耗材 + 备注 -->
        <div class="card">
          <h3 style="margin: 0 0 12px">④ 耗材与备注</h3>
          <el-switch v-model="form.selfFilament" active-text="自备耗材（§16.3：先放保险柜，检验合格后打印）" />
          <div style="margin-top: 12px">
            <div class="muted" style="font-size: 12px; margin-bottom: 6px">给执行打印的负责人留言（可写朝向、支撑、用途要求）</div>
            <el-input v-model="form.note" type="textarea" :rows="3" maxlength="500" show-word-limit
                      placeholder="如：底面请加筏层；这是承力件不要减薄壁厚…" />
          </div>
        </div>
      </div>

      <!-- 右：模型信息 + 提交 -->
      <div style="display: flex; flex-direction: column; gap: 16px; position: sticky; top: 16px">
        <div class="card">
          <h3 style="margin: 0 0 10px">模型与 Val1</h3>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="模型">{{ order?.model_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="尺寸">
              {{ bbox ? bbox.join(' × ') + ' mm' : '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="体积">{{ volume ? volume + ' cm³' : '—' }}</el-descriptions-item>
            <el-descriptions-item label="Val1">
              <el-tag size="small" :type="val1?.flagged ? 'warning' : 'success'" effect="plain">
                {{ val1?.result || '—' }}{{ val1?.flagged ? ` · 标记 ${val1.flagged_items?.length || 0} 项（已人工放行）` : '' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="自备耗材">{{ form.selfFilament ? '是（待检验）' : '平台耗材' }}</el-descriptions-item>
          </el-descriptions>
          <div class="muted" style="font-size: 12px; margin-top: 8px">
            模型文件与摆放姿态会一起附在清单里，负责人据此在 Bambu Studio 中切片与打印。
          </div>
        </div>

        <div class="card">
          <h3 style="margin: 0 0 10px">提交后会发生什么</h3>
          <el-steps direction="vertical" :active="0" style="height: 150px">
            <el-step title="生成打印清单" description="材料 / 强度 / 进阶参数 / 尺寸 / 备注" />
            <el-step title="负责人执行打印" description="下载模型 → 切片 → 上机打印" />
            <el-step title="Val3 实物验收" description="打印完成由负责人验收并通知取件" />
          </el-steps>
        </div>

        <el-button type="primary" size="large" :loading="submitting" @click="submit">
          提交打印需求 · 生成清单
        </el-button>
        <el-button @click="goWorkspace">← 返回摆放调整</el-button>
        <el-button link @click="goOrder">查看订单详情</el-button>
      </div>
    </div>

    <!-- 提交结果：清单 -->
    <el-dialog v-model="resultVisible" width="620px" :close-on-click-modal="false">
      <template #header><b>打印清单已生成</b></template>
      <div v-if="result" style="display: flex; flex-direction: column; gap: 10px">
        <el-alert type="success" :closable="false" show-icon
                  title="打印需求已提交，负责人将在打印清单中看到这条需求"
                  :description="`清单 #${result.job.seq} · 预估 ${result.estimate.weight_g}g / ${Math.round(result.estimate.time_sec / 60)}min（几何估算，非切片结果）`" />
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="材料">{{ result.manifest.material.name }}</el-descriptions-item>
          <el-descriptions-item label="颜色">{{ result.manifest.color }}</el-descriptions-item>
          <el-descriptions-item label="强度">{{ result.manifest.strength.name }}</el-descriptions-item>
          <el-descriptions-item label="层高">{{ result.manifest.params.layer_height }} mm</el-descriptions-item>
          <el-descriptions-item label="壁厚圈数">{{ result.manifest.params.wall_loops }} 圈</el-descriptions-item>
          <el-descriptions-item label="填充">{{ result.manifest.params.infill_density }}%（{{ result.manifest.params.infill_pattern }}）</el-descriptions-item>
          <el-descriptions-item label="自备耗材">{{ result.manifest.self_filament ? '是 · 待检验' : '平台耗材' }}</el-descriptions-item>
          <el-descriptions-item label="尺寸">{{ (result.manifest.bbox || []).join(' × ') }} mm</el-descriptions-item>
        </el-descriptions>
        <div v-if="result.manifest.operator_note" class="muted" style="font-size: 12.5px">
          备注：{{ result.manifest.operator_note }}
        </div>
        <el-button type="primary" style="width: 100%" @click="goOrder">查看订单进度 →</el-button>
      </div>
    </el-dialog>
  </div>
</template>
