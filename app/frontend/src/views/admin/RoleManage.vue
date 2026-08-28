<script setup>
// 角色与权限（决策清单 §9：RBAC 角色可配置、与模块权限解耦）
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const roles = ref([])
const permissions = ref([])
const dialog = ref(false)
const editing = ref({ id: null, name: '', permissions: [] })

async function load() {
  roles.value = (await api.get('/admin/roles')).roles
  permissions.value = (await api.get('/admin/permissions')).permissions
}

function openEdit(role) {
  editing.value = { id: role?.id ?? null, name: role?.name ?? '', permissions: [...(role?.permissions || [])] }
  dialog.value = true
}

async function save() {
  if (!editing.value.name.trim()) return ElMessage.warning('请输入角色名称')
  if (editing.value.id) {
    await api.put(`/admin/roles/${editing.value.id}`, { name: editing.value.name, permissions: editing.value.permissions })
  } else {
    await api.post('/admin/roles', { name: editing.value.name, permissions: editing.value.permissions })
  }
  ElMessage.success('已保存')
  dialog.value = false
  load()
}

onMounted(load)
</script>

<template>
  <div class="page" style="max-width: 900px">
    <h1 class="page-title">角色与权限</h1>
    <p class="page-sub">RBAC：角色 = 权限点集合，与模块解耦，为后续新增角色预留（如审核员/操作员）</p>

    <div style="display: flex; justify-content: flex-end; margin-bottom: 12px">
      <el-button type="primary" @click="openEdit(null)">+ 新建角色</el-button>
    </div>

    <div class="card" style="padding: 0; overflow: hidden">
      <el-table :data="roles">
        <el-table-column prop="name" label="角色" width="160">
          <template #default="{ row }">
            {{ row.name }}
            <el-tag v-if="row.builtin" size="small" effect="plain" style="margin-left: 6px">内置</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="编码" width="120">
          <template #default="{ row }"><span class="mono">{{ row.code }}</span></template>
        </el-table-column>
        <el-table-column label="权限点" min-width="300">
          <template #default="{ row }">
            <el-tag v-for="p in row.permissions" :key="p" size="small" effect="plain" style="margin: 2px 4px 2px 0">
              {{ p }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="" width="80">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialog" :title="editing.id ? '编辑角色' : '新建角色'" width="520px">
      <el-form label-position="top">
        <el-form-item label="角色名称"><el-input v-model="editing.name" /></el-form-item>
        <el-form-item label="权限点">
          <el-checkbox-group v-model="editing.permissions" style="display: grid; grid-template-columns: 1fr 1fr">
            <el-checkbox v-for="p in permissions" :key="p.code" :value="p.code">
              <span :title="p.name">{{ p.code }}</span>
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
