import request from './request'

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

export interface UploadOut {
  file_name: string
  file_size: number
  file_hash: string
  saved_path: string
}

export interface RawFileItem {
  file_name: string
  file_size: number
  modified_at?: string
}

export interface SampleFileItem {
  file_name: string
  file_size: number
}

export interface MetricOption {
  code: string
  name: string
  unit: string
  status: string
}

export interface SuggestedMapping {
  layout: 'wide' | 'long'
  time_column: string
  granularity: string
  metric_columns: Record<string, string>
  metric_column: string | null
  value_column: string | null
  dim_columns: string[]
}

export interface IngestPreview {
  file_name: string
  columns: string[]
  total_rows: number
  rows: Record<string, unknown>[]
  suggested: SuggestedMapping
  known_metrics: MetricOption[]
}

export interface ImportTaskItem {
  id: number
  file_name: string
  layout: string
  granularity: string
  status: string
  total_rows: number
  success_rows: number
  failed_rows: number
  skipped_rows: number
  value_count: number
  metric_codes?: string[] | null
  error_msg?: string | null
  error_detail?: { row: number; message: string }[] | null
  elapsed_ms?: number | null
  created_at?: string | null
  finished_at?: string | null
}

export interface IngestMappingPayload {
  layout: 'wide' | 'long'
  time_column: string
  time_format?: string | null
  granularity: string
  metric_columns?: Record<string, string>
  metric_column?: string | null
  value_column?: string | null
  dim_columns?: string[]
  auto_create_metric?: boolean
  auto_metric_status?: string
}

/** 可导入文件清单（raw 目录 + 示例文件） */
export function fetchIngestFiles() {
  return request.get<any, ApiResponse<{ raw: RawFileItem[]; samples: SampleFileItem[] }>>(
    '/ingest/files',
  )
}

/** 上传文件到服务端 data/raw */
export function uploadIngestFile(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request.post<any, ApiResponse<UploadOut>>('/ingest/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/** 载入内置示例文件（复制到 data/raw） */
export function loadSampleFile(fileName: string) {
  return request.post<any, ApiResponse<UploadOut>>(
    `/ingest/samples/${encodeURIComponent(fileName)}/load`,
  )
}

/** 预览文件结构与建议映射 */
export function previewIngestFile(payload: { file_name: string; limit?: number }) {
  return request.post<any, ApiResponse<IngestPreview>>('/ingest/preview', payload)
}

/** 按映射执行导入 */
export function runIngest(payload: { file_name: string; source_code?: string | null; mapping: IngestMappingPayload }) {
  return request.post<any, ApiResponse<ImportTaskItem>>('/ingest/run', payload)
}

/** 导入任务列表 */
export function fetchImportTasks(params?: { page?: number; page_size?: number }) {
  return request.get<any, ApiResponse<PageResult<ImportTaskItem>>>('/ingest/tasks', { params })
}

/** 导入任务详情 */
export function fetchImportTask(id: number) {
  return request.get<any, ApiResponse<ImportTaskItem>>(`/ingest/tasks/${id}`)
}
