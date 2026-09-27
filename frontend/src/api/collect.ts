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

/** 采集方式目录项 */
export interface CollectMode {
  mode: string
  name: string
  target_label: string
  target_hint: string
  real_fetch: boolean
  description: string
}

/** 可绑定的数据源 */
export interface CollectSource {
  id: number
  code: string
  name: string
  ds_type: string
  status: string
}

/** 字段映射（与数据导入共用语义） */
export interface IngestMapping {
  layout: 'wide' | 'long'
  time_column: string
  time_format?: string | null
  granularity: string
  metric_columns: Record<string, string>
  metric_column?: string | null
  value_column?: string | null
  dim_columns: string[]
  auto_create_metric: boolean
  auto_metric_status?: string
}

/** 采集任务 */
export interface CollectTask {
  id: number
  tenant_id: number
  code: string
  name: string
  source_id?: number | null
  source_name: string
  source_type: string
  collect_mode: string
  target: string
  mapping?: IngestMapping | null
  extra_config?: Record<string, unknown> | null
  schedule_type: string
  interval_minutes: number
  cron_expr?: string | null
  status: string
  last_run_at?: string | null
  next_run_at?: string | null
  run_count: number
  success_count: number
  fail_count: number
  last_status?: string | null
  remark: string
  created_at?: string | null
  updated_at?: string | null
}

/** 采集运行记录 */
export interface CollectRun {
  id: number
  tenant_id: number
  task_id: number
  task_code: string
  task_name: string
  collect_mode: string
  trigger: string
  status: string
  rows_in: number
  rows_written: number
  rows_failed: number
  duration_ms: number
  simulated: boolean
  message: string
  detail?: Record<string, unknown> | null
  started_at?: string | null
  finished_at?: string | null
}

/** 执行趋势点 */
export interface CollectTrendPoint {
  day: string
  total: number
  success: number
  failed: number
}

/** 采集调度总览 */
export interface CollectOverview {
  total_tasks: number
  enabled_tasks: number
  paused_tasks: number
  scheduled_tasks: number
  due_tasks: number
  total_runs: number
  runs_24h: number
  success_24h: number
  failed_24h: number
  success_rate_24h: number
  rows_written_24h: number
  total_rows_written: number
  avg_duration_ms: number
  mode_distribution: Record<string, number>
  status_distribution: Record<string, number>
  trend: CollectTrendPoint[]
  recent_runs: CollectRun[]
  scheduler_enabled: boolean
}

/** 任务写入载荷 */
export interface CollectTaskPayload {
  code: string
  name: string
  source_id?: number | null
  collect_mode: string
  target: string
  mapping?: IngestMapping | null
  extra_config?: Record<string, unknown>
  schedule_type: string
  interval_minutes: number
  cron_expr?: string | null
  status: string
  remark?: string
}

/** ---------------------------------------------------------------- 接口 */

/** 采集方式目录 */
export function fetchCollectModes() {
  return request.get<any, ApiResponse<CollectMode[]>>('/collect/modes')
}

/** 可绑定数据源下拉项 */
export function fetchCollectSources() {
  return request.get<any, ApiResponse<CollectSource[]>>('/collect/sources')
}

/** 采集调度总览（含近 7 日趋势与最近运行） */
export function fetchCollectOverview() {
  return request.get<any, ApiResponse<CollectOverview>>('/collect/overview')
}

/** 采集任务分页列表 */
export function fetchCollectTasks(params: {
  page?: number
  page_size?: number
  status?: string
  collect_mode?: string
  keyword?: string
} = {}) {
  return request.get<any, ApiResponse<PageResult<CollectTask>>>('/collect/tasks', { params })
}

/** 新建采集任务 */
export function createCollectTask(payload: CollectTaskPayload) {
  return request.post<any, ApiResponse<CollectTask>>('/collect/tasks', payload)
}

/** 编辑采集任务（编码不可改） */
export function updateCollectTask(id: number, payload: Partial<CollectTaskPayload>) {
  return request.put<any, ApiResponse<CollectTask>>(`/collect/tasks/${id}`, payload)
}

/** 删除采集任务（运行记录级联清理） */
export function deleteCollectTask(id: number) {
  return request.delete<any, ApiResponse<{ deleted: number; code: string }>>(`/collect/tasks/${id}`)
}

/** 手动执行一次采集 */
export function runCollectTask(id: number) {
  return request.post<any, ApiResponse<CollectRun>>(`/collect/tasks/${id}/run`)
}

/** 启用 / 暂停任务 */
export function toggleCollectTask(id: number) {
  return request.post<any, ApiResponse<CollectTask>>(`/collect/tasks/${id}/toggle`)
}

/** 立即扫描并执行到期任务 */
export function scanCollectDue() {
  return request.post<any, ApiResponse<{ executed: number[]; count: number }>>('/collect/scheduler/scan')
}

/** 运行记录分页列表 */
export function fetchCollectRuns(params: {
  page?: number
  page_size?: number
  task_id?: number
  status?: string
} = {}) {
  return request.get<any, ApiResponse<PageResult<CollectRun>>>('/collect/runs', { params })
}
