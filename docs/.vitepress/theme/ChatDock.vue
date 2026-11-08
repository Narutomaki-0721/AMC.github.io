<script setup>
import { ref,watch } from 'vue'
import { withBase,useRoute } from 'vitepress'
import {api,token,useAccess} from './api.js'
import Access from './Access.vue'
useAccess()
const route=useRoute(),open=ref(false),draft=ref(''),messages=ref([]),busy=ref(false),error=ref('')
watch(token,()=>{messages.value=[]})
async function send(){
 const content=draft.value.trim();if(!content||busy.value)return
 const id=crypto.randomUUID();const history=[...messages.value,{role:'user',content}].slice(-12)
 busy.value=true;error.value=''
 try{const r=await api('/chat',{method:'POST',body:JSON.stringify({id,messages:history.map(({role,content})=>({role,content})),page:route.path})});messages.value=[...history,{role:'assistant',content:r.reply,task:r.task}];draft.value=''}catch(e){error.value=e.message}finally{busy.value=false}
}
</script>
<template><aside v-if="open" class="dock" aria-label="团队 AI"><header><strong>团队 AI</strong><button @click="open=false" aria-label="关闭对话">×</button></header><Access/><template v-if="token"><div class="thread"><p v-if="!messages.length">正在阅读的页面会随请求一起记录。你可以提问，也可以指定要收录的资料。</p><article v-for="(m,i) in messages" :key="i"><b>{{m.role==='user'?'你':'助手'}}</b><p>{{m.content}}</p><a v-if="m.task" :href="withBase('/tasks.html')+'#'+m.task">查看待审批任务 →</a></article></div><form @submit.prevent="send"><textarea v-model="draft" required maxlength="4000" placeholder="想找什么资料？"/><button :disabled="busy">{{busy?'处理中…':'发送'}}</button></form></template><p role="alert">{{error}}</p></aside><button class="ask" @click="open=!open" :aria-expanded="open">问 AI</button></template>
