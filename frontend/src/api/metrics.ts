import request from './request'

/** ---------------------------------------------------------------- 类型 */

export interface OverviewItem {
  code: string
  name: string
  unit: string
  precision: number
  value: number
  prev_value?: number | null
  delta_ratio?: number | null
  stat_time?: string | null
  has_data: boolean
}

export interface OverviewOut {
  stat_date?: string | null
  items: OverviewItem[]
}

export interface MetricDimension {
  id?: number
  code: string
  name: string
  dim_type: string
  source_field?: string | null
  value_scope?: unknown[] | null
}

export interface MetricItem {
  id: number
  tenant_id: number
  code: string
  name: string
  description?: string | null
  metric_type: string
  agg_func: string
  formula?: string | null
  unit: string
  precision: number
  granularity: string
  owner?: string | null
  tags?: string[] | null
  category_id?: number | null
  source_id?: number | null
  status: string
  dimensions: MetricDimension[]
  created_at?: string | null
  updated_at?: string | null
}

export interface PageResult<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface TrendPoint {
  stat_time: string
  value: number
}

export interface TrendOut {
  code: string
  granularity: string
  start?: string | null
  end?: string | null
  points: TrendPoint[]
}

export interface MetricValuePayload {
  stat_time: string
  granularity?: string
  dims?: Record<string, unknown>
  value: number
}

/** ---------------------------------------------------------------- 接口 */

/** 指标总览（首页指标卡） */
export function fetchOverview(params?: { granularity?: string; codes?: string }) {
  return request.get<any, ApiResponse<OverviewOut>>('/metrics/overview', { params })
}

/** 指标定义列表 */
export function fetchMetrics(params?: {
  keyword?: string
  status?: string
  category_id?: number
  page?: number
  page_size?: number
}) {
  return request.get<any, ApiResponse<PageResult<MetricItem>>>('/metrics', { params })
}

/** 指标详情 */
export function fetchMetric(code: string) {
  return request.get<any, ApiResponse<MetricItem>>(`/metrics/${code}`)
}

/** 新建指标 */
export function createMetric(payload: Partial<MetricItem> & { code: string; name: string }) {
  return request.post<any, ApiResponse<MetricItem>>('/metrics', payload)
}

/** 更新指标 */
export function updateMetric(code: string, payload: Partial<MetricItem>) {
  return request.put<any, ApiResponse<MetricItem>>(`/metrics/${code}`, payload)
}

/** 删除指标 */
export function deleteMetric(code: string) {
  return request.delete<any, ApiResponse<{ code: string; deleted: boolean }>>(`/metrics/${code}`)
}

/** 指标趋势 */
export function fetchTrend(code: string, params?: { granularity?: string; start?: string; end?: string }) {
  return request.get<any, ApiResponse<TrendOut>>(`/metrics/${code}/trend`, { params })
}

/** 写入指标值（同「时间+粒度+维度」为覆盖） */
export function upsertMetricValues(code: string, items: MetricValuePayload[]) {
  return request.post<any, ApiResponse<{ code: string; affected: number }>>(`/metrics/${code}/values`, { items })
}
