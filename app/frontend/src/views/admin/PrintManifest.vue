<script setup>
// 打印清单（整页 / 可打印）：执行打印的负责人拿这一页就能干活
// 数据：GET /admin/print-manifest（待打印 + 打印中，含材料/强度/参数/尺寸/估算/用户备注）
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api'
import { useAppStore } from '@/stores'

const app = useAppStore()
const rows = ref([])
const generatedAt = ref('')
const loading = ref(true)
const keyword = ref('')

const list = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return rows.value
  return rows.value.filter(r =>
    String(r.order_id).includes(k) ||
    (r.manifest?.name || '').toLowerCase().includes(k) ||
    (r.manifest?.user || '').toLowerCase().includes(k))
})

async function load() {
  loading.value = true
  try {
    const d = await api.get('/admin/print-manifest')
    rows.value = d.manifests
    generatedAt.value = d.generated_at
  } finally {
    loading.value = false
  }
}

function materialName(id) {
  return app.materials.find(m => m.id === id)?.name || id
}
function printPage() { window.print() }

onMounted(async () => {
  if (!app.meta) await app.loadMeta()
  load()
})
</script>

<template>
  <div class="page manifest-page">
    <div style="display: flex; justify-content: space-between; align-items: end; flex-wrap: wrap; gap: 12px">
      <div>
        <h1 class="page-title">打印清单</h1>
        <p class="page-sub">
          待打印 {{ rows.filter(r => r.job?.status !== 'printing').length }} 条 ·
          打印中 {{ rows.filter(r => r.job?.status === 'printing').length }} 条 ·
          生成于 {{ generatedAt }}
          <span class="muted">（预估值为几何估算，实际以切片结果为准）</span>
        </p>
      </div>
      <div style="display: flex; gap: 8px" class="no-print">
        <el-input v-model="keyword" placeholder="搜索需求号 / 名称 / 用户" size="default" clearable style="width: 220px" />
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="printPage">打印本页</el-button>
      </div>
    </div>

    <div v-loading="loading" style="display: flex; flex-direction: column; gap: 12px; margin-top: 16px">
      <div v-for="r in list" :key="r.order_id" class="card" style="margin: 0; padding: 14px 16px">
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap">
          <div>
            <b style="font-size: 15px">O{{ r.order_id }} · {{ r.manifest?.name || '—' }}</b>
            <span class="muted" style="font-size: 12.5px; margin-left: 8px">{{ r.manifest?.user }}</span>
          </div>
          <div style="display: flex; gap: 6px; align-items: center">
            <el-tag size="small" :type="r.job?.status === 'printing' ? 'warning' : r.job?.status === 'blocked' ? 'danger' : 'info'">
              {{ { queued: '待打印', blocked: '待检验耗材', printing: '打印中' }[r.job?.status] || r.job?.status }}
            </el-tag>
            <span class="mono muted" style="font-size: 12px">
              清单 #{{ r.job?.seq }}
              <span v-if="r.self_filament"> · 自备耗材{{ r.filament_approved ? '（已检）' : '（待检）' }}</span>
            </span>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px 16px; margin-top: 10px">
          <div><span class="muted">材料</span><br /><b>{{ materialName(r.manifest?.material?.id || '') }}</b></div>
          <div>
            <span class="muted">颜色</span><br />
            <span :style="{ display: 'inline-block', width: 12, height: 12, borderRadius: 3, background: r.manifest?.color, marginRight: 6, border: '1px solid var(--line)' }" />
            <span class="mono">{{ r.manifest?.color }}</span>
          </div>
          <div><span class="muted">强度</span><br /><b>{{ r.manifest?.strength?.name || '—' }}</b></div>
          <div><span class="muted">层高 / 壁厚 / 填充</span><br />
            <span class="mono">{{ r.manifest?.params?.layer_height }}mm / {{ r.manifest?.params?.wall_loops }}圈 / {{ r.manifest?.params?.infill_density }}%</span>
          </div>
          <div><span class="muted">尺寸（mm）</span><br /><span class="mono">{{ (r.manifest?.bbox || []).join(' × ') }}</span></div>
          <div><span class="muted">预估耗材 / 时长</span><br />
            <span class="mono">{{ r.job?.est_weight_g }}g / {{ Math.round((r.job?.est_time_sec || 0) / 60) }}min</span>
          </div>
        </div>

        <div v-if="r.manifest?.operator_note" class="muted" style="font-size: 12.5px; margin-top: 8px">
          用户备注：{{ r.manifest.operator_note }}
        </div>
        <div v-if="r.manifest?.params" class="mono muted" style="font-size: 11.5px; margin-top: 6px">
          关键参数：喷嘴 {{ r.manifest.params.nozzle_temperature }}°C · 热床 {{ r.manifest.params.bed_temperature }}°C ·
          外壁 {{ r.manifest.params.outer_wall_speed }}mm/s · 空驶 {{ r.manifest.params.travel_speed }}mm/s ·
          支撑 {{ r.manifest.params.enable_support }} · 图案 {{ r.manifest.params.infill_pattern }}
        </div>
      </div>
      <el-empty v-if="!list.length && !loading" description="清单为空：还没有需求提交打印" :image-size="70" />
    </div>
  </div>
</template>

<style scoped>
@media print {
  .no-print { display: none !important; }
  .manifest-page { max-width: none !important; }
  .card { break-inside: avoid; box-shadow: none !important; border: 1px solid #bbb !important; }
}
</style>
