<script setup>
import {ref,watch,onUnmounted,onMounted,nextTick} from 'vue'
import {api,token,useAccess,login} from './api.js'
import Access from './Access.vue'
useAccess()
const labels={pending:'待审批',rejected:'不同意',running:'同意 · 正在做',failed:'同意 · 完成失败',success:'同意 · 完成成功'}
const filter=ref('pending'),tasks=ref([]),approver=ref(false),err=ref(''),busy=ref(false)
let timer,first=true
function date(v){return v?new Date(v).toLocaleString('zh-CN'):''}
async function refresh(){const current=token.value;if(!current)return
 try{const r=await api('/tasks');if(current!==token.value)return;tasks.value=r.tasks;approver.value=r.approver;err.value=''
 if(first&&location.hash){const t=r.tasks.find(t=>t.id===location.hash.slice(1));if(t){filter.value=t.status;await nextTick();document.getElementById(t.id)?.scrollIntoView()}}first=false
 }catch(e){err.value=e.message}}
async function act(id,action){if(busy.value)return;busy.value=true;try{const r=await api('/tasks/'+id+'/'+action,{method:'POST'});filter.value=r.status;await refresh()}catch(e){err.value=e.message}finally{busy.value=false}}
watch(token,()=>{tasks.value=[];refresh()})
onMounted(()=>{refresh();timer=setInterval(refresh,5000)});onUnmounted(()=>clearInterval(timer))
</script>
<template><main class="atlas"><p class="eyebrow">MCM / ICM</p><h1>团队任务流</h1><Access/><template v-if="token"><button class="logout" @click="login('')">退出团队空间</button><nav class="tabs"><button v-for="(v,k) in labels" :key="k" :aria-pressed="filter===k" @click="filter=k">{{v}} · {{tasks.filter(t=>t.status===k).length}}</button></nav>
<p v-if="!tasks.some(t=>t.status===filter)" class="notice">此分类暂无任务。</p><article v-for="t in tasks.filter(t=>t.status===filter)" :key="t.id" :id="t.id" class="card"><small>{{date(t.created)}} · {{t.author}} · {{t.id.slice(0,8)}}</small><h2>{{t.spec.title}}</h2><p>{{t.request}}</p><p>归档至 {{t.spec.section}} · 目标 {{t.spec.count}} 条</p><p>收录要求：{{t.spec.criteria}}</p><small v-if="t.page">发起页面 {{t.page}}</small><p v-if="t.reviewer">审批人 {{t.reviewer}} · {{date(t.reviewed)}}</p><div v-if="approver&&t.status==='pending'"><button :disabled="busy" @click="act(t.id,'approve')">同意</button> <button :disabled="busy" @click="act(t.id,'reject')">不同意</button></div><button v-if="approver&&t.status==='failed'" :disabled="busy" @click="act(t.id,'retry')">重做</button><details v-for="a in t.attempts" :key="a.n" :open="a.n===t.attempt"><summary>第 {{a.n}} 次 · {{a.stage}}</summary><pre>{{a.log}}</pre><a v-if="a.url" :href="a.url">打开收录页面 →</a></details></article></template><p role="alert">{{err}}</p></main></template>
