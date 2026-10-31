<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const mode = ref('login')
const form = ref({ username: '', password: '', name: '', grade: '', contact: '' })
const loading = ref(false)

async function submit() {
  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(form.value.username, form.value.password)
      ElMessage.success('欢迎回来～')
    } else {
      await auth.register(form.value)
      ElMessage.success('登记成功，欢迎加入本场活动！')
    }
    router.push(route.query.redirect || '/')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="max-width: 420px; margin: 60px auto; padding: 0 20px">
    <div class="card">
      <h2 style="margin: 0 0 4px">{{ mode === 'login' ? '登录' : '活动登记' }}</h2>
      <p class="muted" style="margin: 0 0 20px">
        学号/用户名 + 密码（决策：暴露公网需权限系统）
      </p>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="学号 / 用户名">
          <el-input v-model="form.username" placeholder="学号 / 用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password
                    placeholder="密码" />
        </el-form-item>
        <template v-if="mode === 'register'">
          <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="年级"><el-input v-model="form.grade" placeholder="如 大一" /></el-form-item>
          <el-form-item label="联系方式"><el-input v-model="form.contact" placeholder="邮箱/手机（用于线下对接）" /></el-form-item>
        </template>
        <el-button type="primary" style="width: 100%" :loading="loading" @click="submit">
          {{ mode === 'login' ? '登录' : '登记并登录' }}
        </el-button>
      </el-form>
      <div style="margin-top: 14px; text-align: center" class="muted">
        {{ mode === 'login' ? '第一次参加活动？' : '已有账号？' }}
        <el-link type="primary" @click="mode = mode === 'login' ? 'register' : 'login'">
          {{ mode === 'login' ? '去登记' : '去登录' }}
        </el-link>
      </div>
    </div>
  </div>
</template>
