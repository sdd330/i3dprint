<script setup>
// 站娘问答（§15）：右侧抽屉式面板
// 2026-10 UI 改版：平时收在右边缘（竖排标签 + 箭头），点击从右侧滑出；
//                  顶部按对话状态切换三张立绘：normal / happy / shocked（不出现任何 emoji）
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api'

const step = ref('')
const messages = ref([
  { role: 'bot', text: '你好，我是薇尔莉特（Violet），Violet Print 的站娘。打印流程、模型检查、材料强度、取件问题都可以问我。' },
])
const input = ref('')
const open = ref(false)
const busy = ref(false)
const queueHint = ref('')   // 本地模型并发上限低，排队时给用户提示
// 立绘表情：normal（默认）/ happy（命中知识库或夸夸）/ shocked（被拦截、异常）
const mood = ref('normal')
const PORTRAIT = {
  normal: '/brand/normal.png',
  happy: '/brand/happy.png',
  shocked: '/brand/shocked.png',
}
const MOOD_LABEL = { normal: '薇尔莉特 · 待机', happy: '薇尔莉特 · 开心', shocked: '薇尔莉特 · 惊讶' }
const portrait = computed(() => PORTRAIT[mood.value] || PORTRAIT.normal)

// 动画关键字 → 立绘表情
const ANIM_MOOD = { happy: 'happy', coin: 'happy', magic: 'happy', warn: 'shocked', think: 'normal' }
let moodTimer = null
function setMood(next, revertMs = 0) {
  clearTimeout(moodTimer)
  mood.value = next
  if (revertMs) moodTimer = setTimeout(() => { mood.value = 'normal' }, revertMs)
}

async function ask() {
  const q = input.value.trim()
  if (!q || busy.value) return
  messages.value.push({ role: 'user', text: q })
  input.value = ''
  busy.value = true
  queueHint.value = ''
  // 排队提示：本地模型并发有限（默认 1），先看一眼队列
  try {
    const q0 = await api.get('/qa/llm/queue')
    if ((q0.waiting || 0) > 0 || (q0.running || 0) >= (q0.max_concurrent || 1)) {
      queueHint.value = `前面还有 ${q0.waiting || 0} 个提问在处理，我会按顺序回答`
    }
  } catch { /* 忽略 */ }
  try {
    const d = await api.post('/qa/ask', { question: q, step: step.value })
    messages.value.push({ role: 'bot', text: d.answer })
    if (d.off_topic) setMood('normal', 2500)
    else if (d.queued) setMood('normal', 2500)
    else if (d.supervised) setMood('shocked', 4000)
    else if (ANIM_MOOD[d.animation]) setMood(ANIM_MOOD[d.animation], d.from_kb || d.vector_hit ? 4000 : 0)
    else setMood('normal')
  } catch (e) {
    setMood('shocked', 4000)
    messages.value.push({ role: 'bot', text: '（我这边有点卡住了，稍后再试一次，或者去「使用手册」翻一下。）' })
  } finally {
    busy.value = false
    queueHint.value = ''
  }
}

// 感知当前路由步骤（情境化，§15.2）
const route = useRoute()
const STEP_LABEL = {
  '/create': '创建打印需求', '/manual': '使用手册',
  '/orders': '我的订单', '/': '首页',
}
watch(() => route.path, p => { step.value = STEP_LABEL[p] || '' }, { immediate: true })

function toggle() {
  open.value = !open.value
  if (open.value) setMood('happy', 1200)
}
</script>

<template>
  <div>
    <!-- 收起的竖排标签（点箭头从右侧展开） -->
    <div v-if="!open" class="qa-drawer-tab" title="点这里展开站娘问答" @click="toggle">
      <span class="qa-tab-arrow">‹</span>
      <span class="qa-tab-text">问答 · 薇尔莉特</span>
      <span class="qa-tab-arrow">‹</span>
    </div>

    <transition name="el-slide-right">
      <div v-if="open" class="qa-drawer">
        <div class="qa-drawer-head">
          <div style="flex: 1">
            <div style="font-weight: 700; font-size: 14.5px">站娘问答 · 薇尔莉特 Violet</div>
            <div style="font-size: 11.5px; opacity: 0.86">
              当前步骤：{{ step || '任意' }} · 答不上来可以留言转人工
            </div>
          </div>
          <el-button link class="qa-drawer-close" style="color:#fff" @click="toggle">收起 ›</el-button>
        </div>

        <div class="qa-portrait">
          <img :src="portrait" :alt="MOOD_LABEL[mood]" />
          <span class="qa-portrait-name">{{ MOOD_LABEL[mood] }}</span>
        </div>

        <div class="qa-body">
          <div v-for="(m, i) in messages" :key="i" class="qa-msg" :class="m.role">
            {{ m.text }}
          </div>
          <div v-if="busy" class="qa-typing">
            薇尔莉特正在想…<span v-if="queueHint" style="margin-left: 6px">{{ queueHint }}</span>
          </div>
        </div>

        <div class="qa-input">
          <el-input v-model="input" placeholder="问问打印的事…" @keyup.enter="ask" :disabled="busy" />
          <el-button type="primary" @click="ask" :loading="busy">发送</el-button>
        </div>
        <div class="qa-hint">问什么都可以：材料怎么选、强度什么意思、模型要满足什么条件、多久取件…</div>
      </div>
    </transition>
  </div>
</template>
