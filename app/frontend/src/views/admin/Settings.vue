<script setup>
// 软件设置（P5）：环境变量 / 跨活动全局设置的图形化配置
// 改动即时生效；重启类项（JWT 密钥等）保存后提示重启
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { useAppStore } from '@/stores'

const app = useAppStore()

const groups = ref(null)
const form = reactive({})
const secretSet = reactive({})  // secret 是否已配置（用于占位提示）
const saving = ref(false)

const CATEGORIES = {
  external: { name: '外部服务', desc: 'AI 建模（Tripo）/ 站娘问答（DeepSeek）API 配置，按实际用量计费' },
  slicer: { name: '切片器（暂缓）', desc: 'OrcaSlicer CLI 与 X1C profile —— 在线切片暂停期间本组隐藏，配置保留可随时恢复' },
  service: { name: '服务', desc: '上传限制 / 分析超时 / JWT 密钥（重启类）' },
  misc: { name: '平台声明', desc: '跨活动不变的全局声明' },
}

async function load() {
  const d = await api.get('/admin/settings')
  groups.value = d.groups
  for (const rows of Object.values(d.groups)) {
    for (const r of rows) {
      if (r.value_type === 'secret') {
        form[r.key] = ''  // secret 不载入明文/掩码，输入框留空
        secretSet[r.key] = r.secret_set
      } else {
        form[r.key] = r.value
      }
    }
  }
}

async function save() {
  saving.value = true
  try {
    // secret 留空 = 保持原值，不提交
    const payload = {}
    for (const rows of Object.values(groups.value || {})) {
      for (const r of rows) {
        if (r.value_type === 'secret') {
          if (form[r.key]?.trim()) payload[r.key] = form[r.key]
        } else {
          payload[r.key] = form[r.key]
        }
      }
    }
    const d = await api.put('/admin/settings', { settings: payload })
    const needRestart = d.restart_required || []
    if (needRestart.length) {
      ElMessage.warning(`已保存。以下设置需重启服务生效：${needRestart.join('、')}`)
    } else {
      ElMessage.success('已保存并即时生效')
    }
    load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

// 在线切片暂缓时隐藏切片器设置组（配置仍在库中，恢复只需把 flow.online_slicing 置 true）
const groupsView = computed(() => {
  if (!groups.value) return null
  if (app.flow?.online_slicing) return groups.value
  const { slicer, ...rest } = groups.value
  return rest
})

onMounted(async () => {
  if (!app.meta) await app.loadMeta().catch(() => {})
  load()
})

function cast(v, type) {
  if (type === 'bool') return v === 'true' || v === true
  if (type === 'int') return Number(v) || 0
  if (type === 'float') return Number(v) || 0
  return v
}
</script>

<template>
  <div class="page" style="max-width: 980px">
    <h1 class="page-title">软件设置</h1>
    <p class="page-sub">环境变量与跨活动不变的全局设置，图形化配置（原 .env）· 改动即时生效 · 重启类项保存后需重启</p>

    <div v-if="groupsView">
      <div v-for="(rows, cat) in groupsView" :key="cat" class="card" style="margin-bottom: 16px">
        <h3 style="margin: 0 0 2px">{{ CATEGORIES[cat]?.name || cat }}</h3>
        <p class="muted" style="margin: 0 0 14px; font-size: 12.5px">{{ CATEGORIES[cat]?.desc }}</p>

        <el-form label-position="top" size="small" style="display: grid; grid-template-columns: 1fr 1fr; gap: 0 20px">
          <el-form-item v-for="r in rows" :key="r.key" :label="r.label">
            <template v-if="r.value_type === 'bool'">
              <el-switch :model-value="cast(form[r.key], 'bool')"
                         @update:model-value="v => form[r.key] = String(v)" />
            </template>
            <template v-else-if="r.value_type === 'int' || r.value_type === 'float'">
              <el-input-number :model-value="cast(form[r.key], r.value_type)" :min="0"
                               @update:model-value="v => form[r.key] = String(v)" style="width: 100%" />
            </template>
            <template v-else>
              <el-input :model-value="form[r.key]" :type="r.value_type === 'secret' ? 'password' : 'text'"
                        show-password :placeholder="r.value_type === 'secret' ? (secretSet[r.key] ? '已设置，留空保持不变' : '未设置，可填写') : ''"
                        @update:model-value="v => form[r.key] = v" />
            </template>
            <div class="muted" style="font-size: 11.5px; margin-top: 3px">
              {{ r.hint }}
              <el-tag v-if="r.restart_required" size="small" type="warning" effect="plain" style="margin-left: 6px">重启生效</el-tag>
            </div>
          </el-form-item>
        </el-form>
      </div>

      <el-button type="primary" size="large" :loading="saving" @click="save">保存全部设置</el-button>
      <el-button @click="load">重置编辑</el-button>
    </div>
  </div>
</template>
