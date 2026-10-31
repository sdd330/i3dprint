<script setup>
// 用户管理（负责人）：列表 / 搜索 / 新建 / 改角色 / 启停 / 重置密码 / 删除
// 权限：user:manage；root 为受保护超级管理员（不可改/删/停用，角色也不可编辑）
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const rows = ref([])
const roles = ref([])
const loading = ref(true)
const q = ref('')
const roleFilter = ref(null)
const activeFilter = ref(null)

const ROLE_TAG = { root: 'danger', admin: 'warning', student: 'info' }

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (q.value.trim()) params.set('q', q.value.trim())
    if (roleFilter.value) params.set('role_id', String(roleFilter.value))
    if (activeFilter.value !== null) params.set('active', String(activeFilter.value))
    const d = await api.get(`/admin/users?${params.toString()}`)
    rows.value = d.users
    roles.value = d.roles
  } finally {
    loading.value = false
  }
}

function isProtected(row) {
  return row.username === 'root' || row.role_code === 'root'
}

// —— 新建用户 ——
const createVisible = ref(false)
const creating = ref(false)
const createForm = reactive({ username: '', name: '', password: '', role_id: null, grade: '', contact: '' })
function openCreate() {
  Object.assign(createForm, { username: '', name: '', password: '', role_id: null, grade: '', contact: '' })
  const stu = roles.value.find(r => r.code === 'student')
  createForm.role_id = stu?.id ?? roles.value[0]?.id ?? null
  createVisible.value = true
}
async function submitCreate() {
  if (!createForm.username.trim()) return ElMessage.warning('请填写学号 / 用户名')
  if ((createForm.password || '').length < 6) return ElMessage.warning('初始密码至少 6 位')
  creating.value = true
  try {
    await api.post('/admin/users', { ...createForm })
    ElMessage.success('已创建用户')
    createVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    creating.value = false
  }
}

// —— 编辑用户 ——
const editVisible = ref(false)
const editing = ref(null)
const editForm = reactive({ name: '', grade: '', contact: '', role_id: null, is_active: true })
function openEdit(row) {
  if (isProtected(row)) return ElMessage.info('root 为受保护的超级管理员，不能在此修改')
  editing.value = row
  Object.assign(editForm, {
    name: row.name, grade: row.grade, contact: row.contact, role_id: row.role_id, is_active: row.is_active,
  })
  editVisible.value = true
}
async function submitEdit() {
  try {
    await api.put(`/admin/users/${editing.value.id}`, { ...editForm })
    ElMessage.success('已保存')
    editVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function toggleActive(row) {
  if (isProtected(row)) return
  const next = !row.is_active
  await ElMessageBox.confirm(
    `确认${next ? '启用' : '停用'}「${row.name || row.username}」？${next ? '' : '停用后该账号无法登录。'}`,
    '账号状态'
  )
  try {
    await api.put(`/admin/users/${row.id}`, { is_active: next })
    ElMessage.success(next ? '已启用' : '已停用')
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

// —— 重置密码 ——
const pwdVisible = ref(false)
const pwdTarget = ref(null)
const pwdValue = ref('')
function openReset(row) {
  if (isProtected(row)) return ElMessage.info('root 的口令请由 root 本人用右上角「修改密码」')
  pwdTarget.value = row
  pwdValue.value = ''
  pwdVisible.value = true
}
async function submitReset() {
  if ((pwdValue.value || '').length < 6) return ElMessage.warning('密码至少 6 位')
  try {
    await api.post(`/admin/users/${pwdTarget.value.id}/password`, { password: pwdValue.value })
    ElMessage.success('密码已重置，请通知本人')
    pwdVisible.value = false
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function remove(row) {
  if (isProtected(row)) return
  await ElMessageBox.confirm(`确认删除「${row.username}」？（有需求记录的用户请改用停用）`, '删除用户')
  try {
    await api.del(`/admin/users/${row.id}`)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

const roleName = (id) => roles.value.find(r => r.id === id)?.name || '—'

onMounted(load)
</script>

<template>
  <div class="page">
    <div style="display: flex; justify-content: space-between; align-items: end; flex-wrap: wrap; gap: 12px">
      <div>
        <h1 class="page-title">用户管理</h1>
        <p class="page-sub">
          账号 / 角色 / 启停 / 重置密码。角色与权限点在「角色管理」里配置；
          <b>root</b> 是受保护的超级管理员，不可删除、停用或降级。
        </p>
      </div>
      <div style="display: flex; gap: 8px">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">+ 新建用户</el-button>
      </div>
    </div>

    <div class="card" style="margin-bottom: 14px; padding: 12px 16px">
      <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center">
        <el-input v-model="q" placeholder="搜索学号 / 姓名 / 年级" clearable style="width: 240px"
                  @keyup.enter="load" @clear="load" />
        <el-select v-model="roleFilter" placeholder="全部角色" clearable style="width: 150px" @change="load">
          <el-option v-for="r in roles" :key="r.id" :value="r.id" :label="r.name" />
        </el-select>
        <el-select v-model="activeFilter" placeholder="全部状态" clearable style="width: 130px" @change="load">
          <el-option :value="true" label="已启用" />
          <el-option :value="false" label="已停用" />
        </el-select>
        <el-button @click="load">查询</el-button>
        <span class="muted" style="font-size: 12.5px">共 {{ rows.length }} 个账号</span>
      </div>
    </div>

    <div class="card" style="padding: 0; overflow: hidden">
      <el-table v-loading="loading" :data="rows" style="width: 100%">
        <el-table-column label="账号" min-width="180">
          <template #default="{ row }">
            <div style="font-weight: 600">{{ row.name || row.username }}</div>
            <div class="mono muted" style="font-size: 11.5px">{{ row.username }} · {{ row.grade || '—' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="150">
          <template #default="{ row }">
            <el-tag size="small" :type="ROLE_TAG[row.role_code] || 'info'" effect="plain">{{ row.role_name }}</el-tag>
            <el-tag v-if="isProtected(row)" size="small" type="danger" effect="dark" style="margin-left: 4px">受保护</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="contact" label="联系方式" min-width="160" show-overflow-tooltip />
        <el-table-column label="需求数" width="90">
          <template #default="{ row }"><span class="mono">{{ row.orders }}</span></template>
        </el-table-column>
        <el-table-column label="创建时间" width="150">
          <template #default="{ row }"><span class="mono muted" style="font-size: 11.5px">{{ row.created_at?.slice(0, 16) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="270">
          <template #default="{ row }">
            <template v-if="!isProtected(row)">
              <el-button size="small" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" @click="openReset(row)">重置密码</el-button>
              <el-button size="small" :type="row.is_active ? 'warning' : 'success'" @click="toggleActive(row)">
                {{ row.is_active ? '停用' : '启用' }}
              </el-button>
              <el-button size="small" type="danger" plain @click="remove(row)">删除</el-button>
            </template>
            <span v-else class="muted" style="font-size: 12px">受保护账号（口令请本人修改）</span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="没有匹配的账号" :image-size="60" />
        </template>
      </el-table>
    </div>

    <!-- 新建 -->
    <el-dialog v-model="createVisible" title="新建用户" width="520px">
      <el-form label-position="top">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
          <el-form-item label="学号 / 用户名">
            <el-input v-model="createForm.username" placeholder="如 20261234" />
          </el-form-item>
          <el-form-item label="姓名">
            <el-input v-model="createForm.name" placeholder="如 张同学" />
          </el-form-item>
          <el-form-item label="初始密码（≥6 位）">
            <el-input v-model="createForm.password" type="password" show-password />
          </el-form-item>
          <el-form-item label="角色">
            <el-select v-model="createForm.role_id" style="width: 100%">
              <el-option v-for="r in roles" :key="r.id" :value="r.id" :label="r.name" :disabled="r.code === 'root'" />
            </el-select>
          </el-form-item>
          <el-form-item label="年级">
            <el-input v-model="createForm.grade" placeholder="如 大一" />
          </el-form-item>
          <el-form-item label="联系方式">
            <el-input v-model="createForm.contact" placeholder="手机 / 邮箱" />
          </el-form-item>
        </div>
        <div class="muted" style="font-size: 12px">学生也可以自助注册（登录页「注册」）；root 角色不能直接分配。</div>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑 -->
    <el-dialog v-model="editVisible" :title="`编辑用户 · ${editing?.username}`" width="520px">
      <el-form label-position="top">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
          <el-form-item label="姓名">
            <el-input v-model="editForm.name" />
          </el-form-item>
          <el-form-item label="年级">
            <el-input v-model="editForm.grade" />
          </el-form-item>
          <el-form-item label="联系方式">
            <el-input v-model="editForm.contact" />
          </el-form-item>
          <el-form-item label="角色">
            <el-select v-model="editForm.role_id" style="width: 100%">
              <el-option v-for="r in roles" :key="r.id" :value="r.id" :label="r.name" :disabled="r.code === 'root'" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="账号状态">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="pwdVisible" :title="`重置密码 · ${pwdTarget?.username}`" width="420px">
      <el-form label-position="top">
        <el-form-item label="新密码（≥6 位）">
          <el-input v-model="pwdValue" type="password" show-password />
        </el-form-item>
        <div class="muted" style="font-size: 12px">重置后请通知本人尽快自行修改。</div>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" @click="submitReset">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>
