<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore, useAppStore } from '@/stores'
import QaPanel from '@/components/QaPanel.vue'

const auth = useAuthStore()
const app = useAppStore()
const route = useRoute()

// 全局元数据（材料 / 强度档 / 能力开关 flow）：首页与订单页都要用，统一在这里预载
onMounted(() => { if (!app.meta) app.loadMeta().catch(() => {}) })
</script>

<template>
  <div>
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand" @click="$router.push('/')">
          <span class="brand-logo">🧪</span>
          <span>3D 打印小屋</span>
        </div>
        <nav class="nav">
          <router-link to="/">首页</router-link>
          <router-link to="/orders">我的订单</router-link>
          <router-link to="/create">创建需求</router-link>
          <router-link to="/ai">AI 建模</router-link>
          <router-link to="/manual">使用手册</router-link>
          <template v-if="auth.isAdmin">
            <el-divider direction="vertical" style="margin: 0 6px" />
            <router-link to="/admin">负责人工作台</router-link>
            <router-link to="/admin/config">配置中心</router-link>
            <router-link to="/admin/settings">软件设置</router-link>
          </template>
        </nav>
        <div v-if="auth.isLoggedIn" style="display: flex; align-items: center; gap: 10px">
          <el-tag :type="auth.isAdmin ? 'warning' : 'primary'" effect="plain" round>
            {{ auth.user.name }} · {{ auth.isAdmin ? '负责人' : auth.user.grade }}
          </el-tag>
          <el-button link type="danger" @click="auth.logout(); $router.push('/')">退出</el-button>
        </div>
        <router-link v-else to="/login"><el-button type="primary" size="small">登录</el-button></router-link>
      </div>
    </header>
    <router-view />
    <QaPanel />
  </div>
</template>
