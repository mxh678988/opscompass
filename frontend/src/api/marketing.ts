import request from './request'

/** ---------------------------------------------------------------- 类型 */

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PageResult<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

/** 渠道类型目录项：平台授权方式与开放能力 */
export interface ChannelTypeItem {
  channel_type: string
  name: string
  category: string
  auth_modes: string[]
  abilities: string[]
  platform: string
  connected: number
  authorized: number
}

/** 渠道账号（凭据仅返回脱敏串，不回显明文） */
export interface MarketingChannel {
  id: number
  tenant_id: number
  channel_type: string
  channel_name: string
  account_name: string
  auth_type: string
  credential_masked: string
  api_base: string
  scopes: string
  status: string
  expires_at: string
  last_sync_at: string
  auto_publish: boolean
  remark: string
  created_at?: string | null
  updated_at?: string | null
}

/** 渠道投放 / 分发任务 */
export interface ChannelCampaign {
  id: number
  tenant_id: number
  channel_id: number
  website_id?: number | null
  name: string
  campaign_type: string
  content_title: string
  content_body: string
  target_url: string
  budget_cents: number
  schedule_at: string
  dispatch_mode: string
  status: string
  result: string
  error_message: string
  reach_count: number
  click_count: number
  convert_count: number
  created_at?: string | null
  updated_at?: string | null
}

/** 渠道事件日志 */
export interface ChannelEvent {
  id: number
  tenant_id: number
  channel_id: number
  campaign_id?: number | null
  event_type: string
  level: string
  message: string
  payload: string
  created_at?: string | null
}

/** 渠道接入概览 */
export interface MarketingOverview {
  channels_total: number
  channels_authorized: number
  channels_unauthorized: number
  channels_expired: number
  channels_disabled: number
  campaigns_total: number
  campaigns_pending: number
  campaigns_success: number
  campaigns_failed: number
  events_total: number
  covered_types: string[]
  type_coverage: ChannelTypeItem[]
}

/** ---------------------------------------------------------------- 渠道类型目录 */

/** 渠道类型目录（含各类型已接入 / 已授权数量） */
export function fetchChannelTypes() {
  return request.get<any, ApiResponse<ChannelTypeItem[]>>('/marketing/channel-types')
}

/** 接入概览 */
export function fetchMarketingOverview() {
  return request.get<any, ApiResponse<MarketingOverview>>('/marketing/overview')
}

/** ---------------------------------------------------------------- 渠道账号 */

export interface ChannelCreatePayload {
  channel_type: string
  channel_name: string
  account_name: string
  auth_type?: string
  api_base?: string
  scopes?: string
  auto_publish?: boolean
  remark?: string
  /** 凭据明文：仅写入，不回显 */
  credential?: string
}

/** 渠道账号列表 */
export function fetchChannels(params?: {
  channel_type?: string
  status?: string
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get<any, ApiResponse<PageResult<MarketingChannel>>>('/marketing/channels', { params })
}

/** 新增渠道账号 */
export function createChannel(payload: ChannelCreatePayload) {
  return request.post<any, ApiResponse<MarketingChannel>>('/marketing/channels', payload)
}

/** 编辑渠道账号 */
export function updateChannel(id: number, payload: Partial<MarketingChannel>) {
  return request.put<any, ApiResponse<MarketingChannel>>(`/marketing/channels/${id}`, payload)
}

/** 删除渠道账号（级联删除其投放任务与事件） */
export function deleteChannel(id: number) {
  return request.delete<any, ApiResponse<{ id: number; deleted: boolean }>>(`/marketing/channels/${id}`)
}

/** 写入凭据并授权 */
export function authorizeChannel(
  id: number,
  payload: { credential: string; auth_type?: string; expires_at?: string; scopes?: string },
) {
  return request.post<any, ApiResponse<MarketingChannel>>(`/marketing/channels/${id}/authorize`, payload)
}

/** 撤销授权（清除本地凭据） */
export function revokeChannel(id: number) {
  return request.post<any, ApiResponse<MarketingChannel>>(`/marketing/channels/${id}/revoke`)
}

/** 触发渠道数据同步 */
export function syncChannel(id: number) {
  return request.post<any, ApiResponse<MarketingChannel>>(`/marketing/channels/${id}/sync`)
}

/** ---------------------------------------------------------------- 投放任务 */

export interface CampaignCreatePayload {
  channel_id: number
  name: string
  campaign_type: string
  website_id?: number | null
  content_title?: string
  content_body?: string
  target_url?: string
  budget_cents?: number
  schedule_at?: string
  dispatch_mode?: string
}

/** 投放任务列表 */
export function fetchCampaigns(params?: {
  channel_id?: number
  status?: string
  page?: number
  page_size?: number
}) {
  return request.get<any, ApiResponse<PageResult<ChannelCampaign>>>('/marketing/campaigns', { params })
}

/** 创建投放任务 */
export function createCampaign(payload: CampaignCreatePayload) {
  return request.post<any, ApiResponse<ChannelCampaign>>('/marketing/campaigns', payload)
}

/** 编辑投放任务 */
export function updateCampaign(id: number, payload: Partial<ChannelCampaign>) {
  return request.put<any, ApiResponse<ChannelCampaign>>(`/marketing/campaigns/${id}`, payload)
}

/** 删除投放任务 */
export function deleteCampaign(id: number) {
  return request.delete<any, ApiResponse<{ id: number; deleted: boolean }>>(`/marketing/campaigns/${id}`)
}

/** 执行投放任务（当前为本地编排演练，未调用平台真实 API） */
export function executeCampaign(id: number) {
  return request.post<any, ApiResponse<ChannelCampaign>>(`/marketing/campaigns/${id}/execute`)
}

/** ---------------------------------------------------------------- 事件日志 */

/** 渠道事件日志 */
export function fetchChannelEvents(params?: { channel_id?: number; limit?: number }) {
  return request.get<any, ApiResponse<ChannelEvent[]>>('/marketing/events', { params })
}
