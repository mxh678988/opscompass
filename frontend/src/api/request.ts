import axios from 'axios'

/** 令牌存储键（与 auth store 保持一致） */
const TOKEN_KEY = 'opscompass_token'

/** 统一 axios 实例：后端地址来自环境变量，禁止在组件内硬编码 */
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
})

/** 读取令牌：直接读 localStorage，避免与 store 形成循环依赖 */
export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

/** 请求拦截：统一注入 Bearer 令牌 */
request.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/** 响应拦截：解包 data；401 清理令牌并跳转登录页 */
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status: number | undefined = error?.response?.status
    const detail: unknown = error?.response?.data?.detail

    if (status === 401) {
      clearToken()
      localStorage.removeItem('opscompass_user')
      const current = `${window.location.pathname}${window.location.search}`
      if (!current.startsWith('/login')) {
        window.location.replace(`/login?redirect=${encodeURIComponent(current)}`)
      }
    }

    let message = '请求失败，请稍后重试'
    if (typeof detail === 'string' && detail) {
      message = detail
    } else if (Array.isArray(detail)) {
      message = detail
        .map((item) => (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : ''))
        .filter(Boolean)
        .join('；')
    } else if (status === 403) {
      message = '没有访问该功能的权限'
    }

    error.message = message
    console.error('[request error]', status, message)
    return Promise.reject(error)
  },
)

export default request
