import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  fetchMe,
  login as loginApi,
  logout as logoutApi,
  type LoginResult,
  type UserInfo,
} from '@/api/auth'
import { clearToken, getToken, setToken } from '@/api/request'

const USER_KEY = 'opscompass_user'

/** 读取上次缓存用户信息，避免刷新页面时导航栏闪烁 */
function readCachedUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as UserInfo) : null
  } catch {
    return null
  }
}

/** 认证状态：令牌持久化在 localStorage，权限码由 /auth/me 拉取 */
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(getToken())
  const user = ref<UserInfo | null>(readCachedUser())
  const permissions = ref<string[]>([])

  const isLoggedIn = computed(() => Boolean(token.value))
  const isSuperuser = computed(() => Boolean(user.value?.is_superuser))
  const roles = computed(() => user.value?.roles ?? [])
  const displayName = computed(() => user.value?.full_name || user.value?.username || '未登录')

  function cacheUser(value: UserInfo | null) {
    user.value = value
    if (value) {
      localStorage.setItem(USER_KEY, JSON.stringify(value))
    } else {
      localStorage.removeItem(USER_KEY)
    }
  }

  /** 登录：写入令牌并拉取权限 */
  async function login(username: string, password: string): Promise<LoginResult> {
    const res = await loginApi(username, password)
    token.value = res.data.access_token
    setToken(res.data.access_token)
    cacheUser(res.data.user)
    await loadProfile()
    return res.data
  }

  /** 刷新用户信息与权限码 */
  async function loadProfile(): Promise<void> {
    if (!token.value) return
    const res = await fetchMe()
    cacheUser(res.data.user)
    permissions.value = res.data.permissions ?? []
  }

  /** 权限判断：超级管理员放行全部 */
  function hasPermission(code: string): boolean {
    return isSuperuser.value || permissions.value.includes(code)
  }

  /** 退出登录：无论接口是否成功，本地状态一律清理 */
  async function logout(): Promise<void> {
    try {
      if (token.value) await logoutApi()
    } catch {
      // 忽略登出接口异常
    }
    token.value = ''
    permissions.value = []
    cacheUser(null)
    clearToken()
  }

  return {
    token,
    user,
    permissions,
    isLoggedIn,
    isSuperuser,
    roles,
    displayName,
    login,
    loadProfile,
    hasPermission,
    logout,
  }
})
