import { ref, onMounted } from 'vue'
export const base = (import.meta.env.VITE_API_URL || '').replace(/\/$/,'')
export const token = ref('')
export function useAccess(){onMounted(()=>{token.value=sessionStorage.getItem('member-token')||''})}
export function login(value){token.value=value.trim();sessionStorage.setItem('member-token',token.value)}
export async function api(path,options={}){
  if(!base) throw Error('尚未配置团队 API 地址。')
  const r=await fetch(base+path,{...options,headers:{'Content-Type':'application/json',Authorization:'Bearer '+token.value,...options.headers}})
  const body=await r.json();if(!r.ok)throw Error(body.error || '请求失败');return body
}
