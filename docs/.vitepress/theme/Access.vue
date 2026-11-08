<script setup>
import {ref} from 'vue'
import {token,login,base,api} from './api.js'
const key=ref(''),error=ref(''),busy=ref(false)
async function enter(){busy.value=true;error.value='';try{await api('/me',{headers:{Authorization:'Bearer '+key.value.trim()}});login(key.value);key.value=''}catch(e){error.value=e.message}finally{busy.value=false}}
</script>
<template><div v-if="!base" class="notice">团队 API 尚未连接。知识目录仍可阅读。</div><form v-else-if="!token" @submit.prevent="enter"><label>团队成员访问码<input v-model="key" type="password" required autocomplete="off"></label><button :disabled="busy">进入团队空间</button><p role="alert">{{error}}</p></form></template>
