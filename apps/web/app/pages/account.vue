<script setup lang="ts">
const session = useSessionStore()
const form = reactive({ oldPassword: '', newPassword: '', confirm: '' })
const message = ref('')
const pending = ref(false)

async function submit() {
  message.value = ''
  if (form.newPassword !== form.confirm) {
    message.value = '两次输入的新口令不一致'
    return
  }
  pending.value = true
  try {
    await $fetch('/api/account/password', {
      method: 'POST',
      body: { oldPassword: form.oldPassword, newPassword: form.newPassword },
    })
    form.oldPassword = ''
    form.newPassword = ''
    form.confirm = ''
    message.value = '口令已更新'
  } catch {
    message.value = '没有更新。请核对当前口令，新口令至少 8 位。'
  } finally {
    pending.value = false
  }
}

useSeoMeta({ title: '账号 · Violet Print' })
</script>

<template>
  <div class="max-w-md">
    <h1 class="text-3xl">账号</h1>
    <p v-if="session.user" class="mt-3 text-mute">{{ session.user.name }} · {{ session.user.role }}</p>
    <form class="mt-6 grid gap-4" @submit.prevent="submit">
      <label class="grid gap-2 text-sm text-mute">
        当前口令
        <input v-model="form.oldPassword" class="h-11 rounded-xl border border-line bg-panel px-3 text-paper" type="password" autocomplete="current-password" required />
      </label>
      <label class="grid gap-2 text-sm text-mute">
        新口令
        <input v-model="form.newPassword" class="h-11 rounded-xl border border-line bg-panel px-3 text-paper" type="password" autocomplete="new-password" minlength="8" required />
      </label>
      <label class="grid gap-2 text-sm text-mute">
        再输入一次
        <input v-model="form.confirm" class="h-11 rounded-xl border border-line bg-panel px-3 text-paper" type="password" autocomplete="new-password" minlength="8" required />
      </label>
      <p v-if="message" class="text-sm text-mute" role="status">{{ message }}</p>
      <button class="btn-primary h-11" type="submit" :disabled="pending">更新口令</button>
    </form>
  </div>
</template>
