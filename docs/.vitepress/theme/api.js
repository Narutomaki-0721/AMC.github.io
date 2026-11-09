import { ref, onMounted } from 'vue'

export const base = (import.meta.env.VITE_API_URL || '').replace(/\/$/,'')
export const token = ref('')
export const identity = ref(null)
export const authNotice = ref('')
let restored = false

export function useAccess() {
  onMounted(() => {
    if (restored) return
    restored = true
    // Some privacy modes prohibit storage. An in-memory session still works.
    try { token.value = sessionStorage.getItem('member-token') || '' } catch {}
  })
}

export function login(value, person=null) {
  token.value = value
  identity.value = person
  authNotice.value = ''
  try {
    if (value) sessionStorage.setItem('member-token', value)
    else sessionStorage.removeItem('member-token')
  } catch {}
}

export async function api(path, options={}) {
  if (!base) throw Error('尚未配置团队 API 地址。')
  const current = token.value
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), path==='/chat' ? 75000 : 12000)
  const headers = {Authorization:'Bearer '+current, ...options.headers}
  if (options.body) headers['Content-Type'] = 'application/json'
  try {
    const response = await fetch(base+path, {...options, headers, signal:controller.signal, cache:'no-store'})
    const data = await response.json().catch(() => null)
    if (!response.ok) {
      if (path!=='/me' && current && current===token.value &&
          (response.status===401 || data?.error==='成员访问码无效')) {
        login('')
        authNotice.value='访问码已失效，请重新输入。'
      }
      throw Error(data?.error || '团队服务返回 HTTP '+response.status+'，请重试。')
    }
    if (!data) throw Error('团队服务未返回有效数据，请刷新重试。')
    return data
  } catch (error) {
    if (controller.signal.aborted) throw Error('连接团队服务超时，请检查网络后重试。')
    if (error instanceof TypeError) throw Error('无法连接团队服务。请检查网络是否能访问 '+new URL(base).hostname+'，再重试。')
    throw error
  } finally { clearTimeout(timer) }
}
