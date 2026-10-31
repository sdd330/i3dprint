<script setup>
import { onMounted, ref, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { useAuthStore, useAppStore } from '@/stores'
import QaPanel from '@/components/QaPanel.vue'

const auth = useAuthStore()
const app = useAppStore()
const route = useRoute()

// 全局元数据（材料 / 强度档 / 能力开关 flow）：首页与订单页都要用，统一在这里预载
onMounted(() => { if (!app.meta) app.loadMeta().catch(() => {}) })

// 修改自己的密码
const pwdVisible = ref(false)
const pwdBusy = ref(false)
const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })
async function changePassword() {
  if (pwdForm.new_password.length < 6) return ElMessage.warning('新密码至少 6 位')
  if (pwdForm.new_password !== pwdForm.confirm) return ElMessage.warning('两次输入的新密码不一致')
  pwdBusy.value = true
  try {
    await api.post('/auth/password', { old_password: pwdForm.old_password, new_password: pwdForm.new_password })
    ElMessage.success('密码已修改')
    pwdVisible.value = false
    Object.assign(pwdForm, { old_password: '', new_password: '', confirm: '' })
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    pwdBusy.value = false
  }
}
</script>

<template>
  <div>
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand" @click="$router.push('/')">
          <span class="brand-logo"><img src="/brand/sign.jpg" alt="VIOLET Z" /></span>
          <span class="brand-name">
            Violet Print
            <small>TEAM 6940 · 校园 3D 打印自助平台</small>
          </span>
        </div>
        <nav class="nav">
          <router-link to="/">首页</router-link>
          <router-link to="/orders">我的订单</router-link>
          <router-link to="/create">创建需求</router-link>
          <router-link v-if="app.flow.ai_modeling" to="/ai">AI 建模</router-link>
          <router-link to="/manual">使用手册</router-link>
          <template v-if="auth.isAdmin">
            <el-divider direction="vertical" style="margin: 0 6px" />
            <router-link to="/admin">负责人工作台</router-link>
            <router-link to="/admin/campaigns">活动管理</router-link>
            <router-link to="/admin/users">用户管理</router-link>
            <router-link to="/admin/roles">角色权限</router-link>
            <router-link to="/admin/config">配置中心</router-link>
            <router-link to="/admin/settings">软件设置</router-link>
          </template>
        </nav>
        <div v-if="auth.isLoggedIn" style="display: flex; align-items: center; gap: 10px">
          <el-tag :type="auth.isAdmin ? 'warning' : 'primary'" effect="plain" round>
            {{ auth.user.name }} · {{ auth.isAdmin ? '负责人' : auth.user.grade }}
          </el-tag>
          <el-button link @click="pwdVisible = true">修改密码</el-button>
          <el-button link type="danger" @click="auth.logout(); $router.push('/')">退出</el-button>
        </div>
        <router-link v-else to="/login"><el-button type="primary" size="small">登录</el-button></router-link>
      </div>
    </header>
    <!-- 队徽底纹：固定在左侧，低透明度（sign.jpg） -->
    <div class="brand-watermark" aria-hidden="true" />
    <router-view />
    <!-- 修改密码（所有人） -->
    <el-dialog v-model="pwdVisible" title="修改密码" width="420px">
      <el-form label-position="top">
        <el-form-item label="当前密码">
          <el-input v-model="pwdForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码（≥6 位）">
          <el-input v-model="pwdForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="pwdForm.confirm" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdBusy" @click="changePassword">确认修改</el-button>
      </template>
    </el-dialog>
    <QaPanel />
  </div>
</template>
