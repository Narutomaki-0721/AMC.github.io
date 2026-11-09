<script setup>
import { ref } from 'vue'
import { token, identity, authNotice, login, base, api } from './api.js'

const key = ref(''), error = ref(''), busy = ref(false)
async function enter() {
  if (busy.value) return
  error.value = ''
  authNotice.value = ''
  const pasted = key.value.trim().replace(/[\u200b\ufeff]/g,'').trim()
  // Accept one row from the private TSV roster as well as the code column.
  const row = pasted.match(/^(?:owner|member-\d+)\s+(?:approver|member)\s+([A-Fa-f0-9]{64})$/)
  const code = row ? row[1] : pasted
  if (!code || /\s/.test(code) || code.length<16 || code.length>256) {
    error.value = '请输入访问码，或从清单复制你自己的一行。'
    return
  }
  busy.value = true
  try {
    const person = await api('/me', {headers:{Authorization:'Bearer '+code}})
    if (!person?.name || typeof person.approver !== 'boolean') throw Error('成员验证未完成，请重试。')
    login(code, person)
    key.value = ''
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
</script>
<template>
  <div v-if="!base" class="notice">团队 API 尚未连接。知识目录仍可阅读。</div>
  <form v-else-if="!token" @submit.prevent="enter" :aria-busy="busy">
    <label>团队成员访问码<input v-model="key" type="password" :disabled="busy" autocomplete="off" autocapitalize="none" spellcheck="false"></label>
    <button type="submit" :disabled="busy">{{busy ? '正在验证访问码…' : '进入团队空间'}}</button>
    <p v-if="error || authNotice" role="alert">{{error || authNotice}}</p>
  </form>
  <div v-else class="member-session">
    <span role="status">{{ identity ? identity.name+' · '+(identity.approver?'审批人':'普通队员') : '已进入团队空间' }}</span>
    <button type="button" @click="login('')">退出此标签页</button>
  </div>
</template>
