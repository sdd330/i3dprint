<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores'
import { api } from '@/api'

const auth = useAuthStore()
const step = ref('')
const messages = ref([
  { role: 'bot', text: '你好呀～我是 3D 打印小屋的站娘店长，打印流程、参数、费用、取件的问题都可以问我！' },
])
const input = ref('')
const open = ref(false)
const busy = ref(false)

async function ask() {
  const q = input.value.trim()
  if (!q || busy.value) return
  messages.value.push({ role: 'user', text: q })
  input.value = ''
  busy.value = true
  try {
    const d = await api.post('/qa/ask', { question: q, step: step.value })
    messages.value.push({ role: 'bot', text: d.answer })
  } catch (e) {
    messages.value.push({ role: 'bot', text: '（站娘走神了，稍后再试～）' })
  } finally {
    busy.value = false
  }
}

// 感知当前路由步骤（情境化，§15.2）
const route = useRoute()
const STEP_LABEL = {
  '/create': '创建打印需求', '/ai': 'AI 建模', '/manual': '使用手册',
  '/orders': '我的订单', '/': '首页',
}
watch(() => route.path, p => { step.value = STEP_LABEL[p] || '' }, { immediate: true })
</script>

<template>
  <div>
    <transition name="el-zoom-in-top">
      <div v-if="open" class="qa-panel">
        <div class="qa-head">
          <span class="qa-avatar">🧑‍🔧</span>
          <div style="flex: 1">
            <div style="font-weight: 700">站娘 · 店长</div>
            <div style="font-size: 11.5px; opacity: 0.85">当前步骤：{{ step || '任意' }} · 答不上来可以留言哦</div>
          </div>
          <el-button link style="color:#fff" @click="open = false">✕</el-button>
        </div>
        <div class="qa-body">
          <div v-for="(m, i) in messages" :key="i" class="qa-msg" :class="m.role">
            {{ m.text }}
          </div>
          <div v-if="busy" class="qa-typing">站娘思考中…</div>
        </div>
        <div class="qa-input">
          <el-input v-model="input" placeholder="问问打印的事…" @keyup.enter="ask" :disabled="busy" />
          <el-button type="primary" @click="ask" :loading="busy">发送</el-button>
        </div>
      </div>
    </transition>
    <el-button class="qa-fab" circle size="large" type="warning" @click="open = !open">
      <span style="font-size: 20px">🧑‍🔧</span>
    </el-button>
  </div>
</template>
