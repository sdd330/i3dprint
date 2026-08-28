<script setup>
// 站娘配置（决策清单 §13）：知识库条目 / System Prompt / 过滤词
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const tab = ref('kb')
const items = ref([])
const template = ref(null)
const qaCfg = ref(null)
const filterWords = ref('')
const systemPrompt = ref('')

async function load() {
  items.value = (await api.get('/qa/knowledge')).items
  template.value = (await api.get('/admin/config/template')).template
  qaCfg.value = template.value.data.qa
  systemPrompt.value = qaCfg.value.system_prompt
  filterWords.value = (qaCfg.value.filter_words || []).join('\n')
}

const dialog = ref(false)
const editing = ref({ id: null, keywords: [], answer: '', step_context: '', animation_key: '', enabled: true })
const keywordText = ref('')

function openEdit(item) {
  editing.value = item ? { ...item, keywords: [...item.keywords] } : { id: null, keywords: [], answer: '', step_context: '', animation_key: '', enabled: true }
  keywordText.value = (editing.value.keywords || []).join('、')
  dialog.value = true
}

async function saveItem() {
  const body = {
    keywords: keywordText.value.split(/[、,\s]+/).filter(Boolean),
    question: editing.value.question || '',
    answer: editing.value.answer,
    step_context: editing.value.step_context,
    animation_key: editing.value.animation_key,
    enabled: editing.value.enabled,
  }
  if (editing.value.id) await api.put(`/qa/knowledge/${editing.value.id}`, body)
  else await api.post('/qa/knowledge', body)
  ElMessage.success('知识库已更新（即时生效）')
  dialog.value = false
  load()
}

async function del(item) {
  await api.del(`/qa/knowledge/${item.id}`)
  ElMessage.success('已删除')
  load()
}

async function savePrompt() {
  await api.put('/admin/config/template/qa', { data: { ...qaCfg.value, system_prompt: systemPrompt.value, filter_words: filterWords.value.split('\n').map(s => s.trim()).filter(Boolean) } })
  ElMessage.success('已保存（后续会话生效）')
  load()
}
</script>

<template>
  <div class="page" style="max-width: 980px">
    <h1 class="page-title">站娘问答配置</h1>
    <p class="page-sub">知识库 / System Prompt / 过滤词 · 图形化配置，改动即时生效（§15.2 / 决策清单 §13）</p>

    <el-tabs v-model="tab">
      <el-tab-pane label="知识库条目" name="kb">
        <div style="display: flex; justify-content: flex-end; margin-bottom: 12px">
          <el-button type="primary" @click="openEdit(null)">+ 新增条目</el-button>
        </div>
        <div class="card" style="padding: 0; overflow: hidden">
          <el-table :data="items">
            <el-table-column prop="question" label="触发示例" width="180" />
            <el-table-column label="关键词" width="220">
              <template #default="{ row }">
                <el-tag v-for="k in row.keywords" :key="k" size="small" effect="plain" style="margin: 1px 3px">{{ k }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="step_context" label="步骤上下文" width="120" />
            <el-table-column label="动画" width="80">
              <template #default="{ row }">{{ row.animation_key || '—' }}</template>
            </el-table-column>
            <el-table-column prop="answer" label="回答" min-width="240" show-overflow-tooltip />
            <el-table-column label="" width="110">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button link type="danger" @click="del(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <p class="muted" style="font-size: 12.5px; margin-top: 8px">Spine 动画关键字：命中该条时站娘播放对应动画（形象资产后续接入，接口已预留）</p>
      </el-tab-pane>

      <el-tab-pane label="System Prompt / 过滤词" name="prompt">
        <div class="card">
          <h3 style="margin: 0 0 6px">System Prompt（支持变量占位）</h3>
          <p class="muted" style="font-size: 12.5px; margin: 0 0 8px">变量：{step} 当前步骤 · {statement} 合规声明。自监督指令与过滤拦截由系统自动追加。</p>
          <el-input v-model="systemPrompt" type="textarea" :rows="6" />
          <h3 style="margin: 16px 0 6px">过滤词（输入/输出双向检测，命中注入警示并拦截）</h3>
          <el-input v-model="filterWords" type="textarea" :rows="4" placeholder="每行一个过滤词" />
          <el-button type="primary" style="margin-top: 12px" @click="savePrompt">保存</el-button>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="dialog" :title="editing.id ? '编辑知识库条目' : '新增知识库条目'" width="560px">
      <el-form label-position="top">
        <el-form-item label="触发关键词（用、或逗号分隔）">
          <el-input v-model="keywordText" placeholder="如：费用,多少钱,收费" />
        </el-form-item>
        <el-form-item label="回答内容">
          <el-input v-model="editing.answer" type="textarea" :rows="4" />
        </el-form-item>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
          <el-form-item label="步骤上下文（情境化）">
            <el-input v-model="editing.step_context" placeholder="如：参数设置 / Val2 审核" />
          </el-form-item>
          <el-form-item label="Spine 动画关键字">
            <el-input v-model="editing.animation_key" placeholder="如：happy / think / warn" />
          </el-form-item>
        </div>
        <el-form-item label="启用">
          <el-switch v-model="editing.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="saveItem">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
