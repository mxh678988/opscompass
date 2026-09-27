import request from './request'

/** 后端统一响应包装 */
export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
}

/** 当前登录用户信息（与后端 UserOut 对齐） */
export interface UserInfo {
  id: number
  tenant_id?: number | null
  username: string
  full_name?: string | null
  email?: string | null
  is_active: boolean
  is_superuser: boolean
  roles: string[]
  last_login_at?: string | null
  created_at?: string | null
}

/** 登录响应（与后端 TokenOut 对齐） */
export interface LoginResult {
  access_token: string
  token_type: string
  expires_in: number
  user: UserInfo
}

/** 登录 */
export function login(username: string, password: string) {
  return request.post<unknown, ApiEnvelope<LoginResult>>('/auth/login', { username, password })
}

/** 退出登录（记录审计日志，令牌由前端清除） */
export function logout() {
  return request.post<unknown, ApiEnvelope<{ message: string }>>('/auth/logout')
}

/** 当前用户信息 + 权限码 */
export function fetchMe() {
  return request.get<unknown, ApiEnvelope<{ user: UserInfo; permissions: string[] }>>('/auth/me')
}

/** 修改密码 */
export function changePassword(oldPassword: string, newPassword: string) {
  return request.post<unknown, ApiEnvelope<{ message: string }>>('/auth/password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
