import request from './request'
import type { ApiResponse } from './metrics'

/** ============================== 类型定义 ============================== */

export interface ComPlan {
  id: number
  tenant_id: number
  code: string
  name: string
  edition: string
  billing_cycle: string
  price: number
  currency: string
  seats_limit: number
  store_limit: number
  metric_limit: number
  user_limit: number
  ai_quota: number
  features: string[]
  is_public: boolean
  sort: number
  status: string
  remark: string
  created_at?: string | null
  updated_at?: string | null
}

export interface ComLicense {
  id: number
  tenant_id: number
  plan_id?: number | null
  plan_code: string
  plan_name: string
  license_key: string
  license_type: string
  edition: string
  status: string
  seats: number
  machine_code: string
  issued_to: string
  channel: string
  signature: string
  payload: Record<string, unknown>
  issued_at?: string | null
  activated_at?: string | null
  expires_at?: string | null
  days_left?: number | null
  expiring_soon: boolean
  expired: boolean
  remark: string
  created_at?: string | null
  updated_at?: string | null
}

export interface ComOrder {
  id: number
  tenant_id: number
  order_no: string
  plan_id?: number | null
  license_id?: number | null
  plan_code: string
  plan_name: string
  amount: number
  currency: string
  status: string
  pay_channel: string
  buyer: string
  contact: string
  paid_at?: string | null
  remark: string
  created_at?: string | null
  updated_at?: string | null
}

export interface ComUsage {
  id: number
  tenant_id: number
  metric_key: string
  period: string
  used: number
  quota: number
  unit: string
  status: string
  ratio?: number | null
  note: string
  created_at?: string | null
  updated_at?: string | null
}

export interface ComEvent {
  id: number
  license_id?: number | null
  license_key: string
  action: string
  detail: string
  operator: string
  created_at?: string | null
}

export interface ComOverview {
  plans: { total: number; on_sale: number }
  licenses: {
    total: number
    active: number
    pending: number
    expiring_soon: number
    expired: number
    revoked: number
  }
  orders: {
    total: number
    paid: number
    pending: number
    revenue_total: number
    revenue_month: number
    recent: ComOrder[]
  }
  usage: { period: string; warning: number; exceeded: number; items: ComUsage[] }
  events: ComEvent[]
  modes: { key: string; name: string; desc: string }[]
  launch_checklist: { key: string; label: string; hint: string }[]
  currency: string
}

export interface ComEntitlement {
  licensed: boolean
  license?: ComLicense | null
  plan?: ComPlan | null
  limits: {
    seats: number
    stores: number
    metrics: number
    users: number
    ai_quota: number
  }
  usage: { period: string; items: ComUsage[] }
  hint: string
}

export interface ComVerifyResult {
  valid: boolean
  reason: string
  license?: ComLicense
  plan?: ComPlan | null
}

export interface ComPaged<T> {
  total: number
  page: number
  page_size: number
  items: T[]
  summary?: { warning: number; exceeded: number }
}

/** ============================== 接口定义 ============================== */

/** 商业化总览（套餐/授权/订单/收入/用量告警/上架门槛） */
export function fetchOverview() {
  return request.get<any, ApiResponse<ComOverview>>('/commercial/overview')
}

/** 当前租户权益（生效授权 + 套餐限额 + 本月用量对账） */
export function fetchEntitlement() {
  return request.get<any, ApiResponse<ComEntitlement>>('/commercial/entitlement')
}

/** ---------------- 套餐 ---------------- */

export function fetchPlans(
  params: { keyword?: string; edition?: string; page?: number; size?: number } = {},
) {
  return request.get<any, ApiResponse<ComPaged<ComPlan>>>('/commercial/plans', { params })
}

export function createPlan(payload: Partial<ComPlan>) {
  return request.post<any, ApiResponse<ComPlan>>('/commercial/plans', payload)
}

export function updatePlan(id: number, payload: Partial<ComPlan>) {
  return request.patch<any, ApiResponse<ComPlan>>(`/commercial/plans/${id}`, payload)
}

export function deletePlan(id: number) {
  return request.delete<any, ApiResponse<{ id: number; deleted: boolean }>>(`/commercial/plans/${id}`)
}

/** 重建内置套餐（社区版/专业版/旗舰版/SaaS 订阅） */
export function seedPlans() {
  return request.post<any, ApiResponse<{ created: number }>>('/commercial/plans/seed')
}

/** ---------------- 授权 ---------------- */

export function fetchLicenses(
  params: {
    keyword?: string
    status?: string
    license_type?: string
    page?: number
    size?: number
  } = {},
) {
  return request.get<any, ApiResponse<ComPaged<ComLicense>>>('/commercial/licenses', { params })
}

export function issueLicense(payload: {
  plan_id?: number | null
  license_type?: string
  seats?: number
  machine_code?: string
  issued_to?: string
  channel?: string
  days?: number
  remark?: string
}) {
  return request.post<any, ApiResponse<ComLicense>>('/commercial/licenses', payload)
}

export function activateLicense(id: number, machineCode = '') {
  return request.post<any, ApiResponse<ComLicense>>(`/commercial/licenses/${id}/activate`, undefined, {
    params: { machine_code: machineCode },
  })
}

export function renewLicense(id: number, days: number, remark = '') {
  return request.post<any, ApiResponse<ComLicense>>(`/commercial/licenses/${id}/renew`, { days, remark })
}

export function revokeLicense(id: number, reason = '') {
  return request.post<any, ApiResponse<ComLicense>>(`/commercial/licenses/${id}/revoke`, undefined, {
    params: { reason },
  })
}

/** 校验授权（签名 / 状态 / 有效期 / 机器码四重校验，可离线复算） */
export function verifyLicense(payload: { license_key: string; machine_code?: string }) {
  return request.post<any, ApiResponse<ComVerifyResult>>('/commercial/license/verify', payload)
}

/** 授权事件留痕 */
export function fetchEvents(limit = 20) {
  return request.get<any, ApiResponse<{ items: ComEvent[] }>>('/commercial/events', {
    params: { limit },
  })
}

/** ---------------- 订单 ---------------- */

export function fetchOrders(
  params: { keyword?: string; status?: string; page?: number; size?: number } = {},
) {
  return request.get<any, ApiResponse<ComPaged<ComOrder>>>('/commercial/orders', { params })
}

export function createOrder(payload: {
  plan_id?: number
  buyer?: string
  contact?: string
  pay_channel?: string
  remark?: string
}) {
  return request.post<any, ApiResponse<ComOrder>>('/commercial/orders', payload)
}

/** 订单支付（成功后自动签发授权） */
export function payOrder(
  id: number,
  payload: { pay_channel?: string; machine_code?: string; days?: number; remark?: string } = {},
) {
  return request.post<any, ApiResponse<ComOrder>>(`/commercial/orders/${id}/pay`, payload)
}

export function cancelOrder(id: number, reason = '') {
  return request.post<any, ApiResponse<ComOrder>>(`/commercial/orders/${id}/cancel`, undefined, {
    params: { reason },
  })
}

/** ---------------- 用量 ---------------- */

export function fetchUsage(params: { period?: string; page?: number; size?: number } = {}) {
  return request.get<any, ApiResponse<ComPaged<ComUsage>>>('/commercial/usage', { params })
}

export function upsertUsage(payload: {
  metric_key: string
  period: string
  used?: number | null
  delta?: number
  quota?: number | null
  unit?: string
  note?: string
}) {
  return request.post<any, ApiResponse<ComUsage>>('/commercial/usage', payload)
}
