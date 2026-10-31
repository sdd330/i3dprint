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

// —— AI 对话模型（通用 OpenAI 兼容端点：LM Studio / DeepSeek / OpenAI…）——
const llm = ref(null)
const llmLoading = ref(false)
const llmModel = ref('')
const llmBusy = ref(false)
const llmTestQ = ref('用一句话说明 PLA 是什么材料')
const llmTestOut = ref(null)

async function loadLlm() {
  llmLoading.value = true
  try {
    llm.value = await api.get('/admin/llm/status')
    llmModel.value = llm.value.active_model || ''
  } catch (e) {
    llm.value = { reachable: false, error: e.message, chat_models: [] }
  } finally {
    llmLoading.value = false
  }
}
async function saveLlmModel() {
  if (!llmModel.value) return ElMessage.warning('请选择模型')
  llmBusy.value = true
  try {
    await api.post('/admin/llm/model', { model: llmModel.value })
    ElMessage.success(`已切换对话模型：${llmModel.value}`)
    loadLlm()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    llmBusy.value = false
  }
}
async function testLlm() {
  llmBusy.value = true
  llmTestOut.value = null
  try {
    llmTestOut.value = await api.post('/admin/llm/test', { question: llmTestQ.value })
  } catch (e) {
    llmTestOut.value = { ok: false, error: e.message }
  } finally {
    llmBusy.value = false
  }
}

// —— 教材/手册向量知识库（backend/kb/*.md，本地 TF-IDF 检索）——
const kbSources = ref([])
const kbBusy = ref(false)
const kbQuery = ref('')
const kbHits = ref([])
const kbSearching = ref(false)

async function loadKb() {
  kbSources.value = (await api.get('/admin/kb')).sources
}
async function syncKb(force = false) {
  kbBusy.value = true
  try {
    const d = await api.post(`/admin/kb/sync${force ? '?force=true' : ''}`, {})
    const changed = (d.synced || []).filter(x => x.changed)
    ElMessage.success(changed.length
      ? `已重建：${changed.map(x => `${x.name}（${x.chunks} 块）`).join('、')}`
      : '内容未变化，无需重建')
    loadKb()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    kbBusy.value = false
  }
}
async function kbTest() {
  if (!kbQuery.value.trim()) return
  kbSearching.value = true
  try {
    kbHits.value = (await api.post('/admin/kb/search', { question: kbQuery.value, top_k: 3 })).hits
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    kbSearching.value = false
  }
}

async function load() {
  loadKb().catch(() => {})
  loadLlm().catch(() => {})
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

      <el-tab-pane label="教材知识库（向量）" name="vector">
        <div class="card" style="margin-bottom: 12px">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px">
            <div>
              <h3 style="margin: 0 0 4px">教材 / 手册向量索引</h3>
              <p class="muted" style="margin: 0; font-size: 12.5px">
                放在 backend/kb/ 下的 Markdown 会被切块并建立 TF-IDF 向量索引；站娘回答时先查关键词条目，
                未命中则查这里（命中即作答并标注章节出处，不消耗 token）。
              </p>
            </div>
            <div style="display: flex; gap: 8px">
              <el-button :loading="kbBusy" @click="syncKb(false)">同步（增量）</el-button>
              <el-button :loading="kbBusy" @click="syncKb(true)">强制重建</el-button>
            </div>
          </div>
          <el-table :data="kbSources" size="small" style="margin-top: 12px">
            <el-table-column prop="name" label="文件" min-width="220" />
            <el-table-column prop="chunks" label="切块数" width="90" />
            <el-table-column prop="tokens" label="词表规模" width="100" />
            <el-table-column prop="updated_at" label="更新时间" width="180" />
          </el-table>
          <el-empty v-if="!kbSources.length" description="还没有导入任何教材（backend/kb/*.md）" :image-size="50" />
        </div>

        <div class="card">
          <h3 style="margin: 0 0 8px">检索调试（看看学生会问的问题能不能命中）</h3>
          <div style="display: flex; gap: 8px">
            <el-input v-model="kbQuery" placeholder="如：STEP 和 STL 差在哪" @keyup.enter="kbTest" />
            <el-button type="primary" :loading="kbSearching" @click="kbTest">检索</el-button>
          </div>
          <div v-for="(h, i) in kbHits" :key="i" style="border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin-top: 10px">
            <div style="display: flex; justify-content: space-between; gap: 8px">
              <b style="font-size: 13px">{{ h.heading }}</b>
              <span class="mono muted" style="font-size: 12px">相似度 {{ h.score }}</span>
            </div>
            <div class="muted" style="font-size: 12.5px; margin-top: 4px">{{ h.content.slice(0, 160) }}…</div>
          </div>
          <el-empty v-if="!kbHits.length && kbQuery && !kbSearching" description="未命中（会交给大模型回答）" :image-size="50" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="对话模型（LLM）" name="llm">
        <div class="card" style="margin-bottom: 12px" v-loading="llmLoading">
          <div style="display: flex; justify-content: space-between; align-items: start; flex-wrap: wrap; gap: 10px">
            <div>
              <h3 style="margin: 0 0 4px">对话端点</h3>
              <p class="muted" style="margin: 0; font-size: 12.5px">
                任意 OpenAI 兼容 <code>/v1</code> 端点（LM Studio、Ollama、DeepSeek、OpenAI、vLLM…）。
                地址与 API Key 在「软件设置 → 外部服务」里改，这里负责选模型。
              </p>
            </div>
            <el-button size="small" @click="loadLlm">刷新</el-button>
          </div>
          <el-descriptions :column="2" size="small" border style="margin-top: 12px">
            <el-descriptions-item label="Endpoint">{{ llm?.base_url || '—' }}</el-descriptions-item>
            <el-descriptions-item label="连通性">
              <el-tag size="small" :type="llm?.reachable ? 'success' : 'danger'">
                {{ llm?.reachable ? '可达' : '不可达' }}
              </el-tag>
              <span v-if="llm?.has_api_key" class="muted" style="font-size: 12px; margin-left: 6px">已配置 Key</span>
            </el-descriptions-item>
            <el-descriptions-item label="当前模型">{{ llm?.active_model || '（未选择）' }}</el-descriptions-item>
            <el-descriptions-item label="模型数">{{ (llm?.chat_models || []).length }} 个对话模型</el-descriptions-item>
          </el-descriptions>
          <el-alert v-if="llm?.error" type="warning" :closable="false" show-icon style="margin-top: 10px"
                    :title="`端点异常：${llm.error}`" description="检查「软件设置 → 外部服务」里的 Endpoint；本地服务需先在 LM Studio 里开启 Local Server。" />
        </div>

        <div class="card" style="margin-bottom: 12px">
          <h3 style="margin: 0 0 8px">切换模型</h3>
          <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center">
            <el-select v-model="llmModel" style="width: 340px" placeholder="选择一个对话模型" filterable allow-create>
              <el-option v-for="m in llm?.chat_models || []" :key="m" :value="m" :label="m" />
            </el-select>
            <el-button type="primary" :loading="llmBusy" @click="saveLlmModel">切换并保存</el-button>
            <span class="muted" style="font-size: 12px">
              embedding 模型（{{ (llm?.all_models || []).length - (llm?.chat_models || []).length }} 个）已自动过滤，不会出现在这里
            </span>
          </div>
          <p class="muted" style="margin: 8px 0 0; font-size: 12px">
            也可以直接填一个模型名再点保存（有些服务不返回列表）。切换后站娘问答立即使用新模型。
          </p>
        </div>

        <div class="card">
          <h3 style="margin: 0 0 8px">试跑一次</h3>
          <div style="display: flex; gap: 8px">
            <el-input v-model="llmTestQ" placeholder="随便问一句，确认端点和模型可用" @keyup.enter="testLlm" />
            <el-button type="primary" :loading="llmBusy" @click="testLlm">测试</el-button>
          </div>
          <div v-if="llmTestOut" style="margin-top: 10px">
            <el-alert v-if="!llmTestOut.ok" type="error" :closable="false" show-icon
                      :title="llmTestOut.error || '调用失败'" />
            <template v-else>
              <div class="muted" style="font-size: 12px; margin-bottom: 6px">
                模型 {{ llmTestOut.model }} · 耗时 {{ llmTestOut.elapsed_ms }}ms ·
                tokens 入{{ llmTestOut.usage?.in }} / 出{{ llmTestOut.usage?.out }}
              </div>
              <div class="card" style="padding: 12px; margin: 0; white-space: pre-wrap">{{ llmTestOut.answer }}</div>
            </template>
          </div>
        </div>
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
            <el-input v-model="editing.step_context" placeholder="如：参数设置 / 打印需求" />
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
