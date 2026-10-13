import request from './request'
import type { ApiResponse } from './metrics'

/** M14 压缩安全中心：导入解压 / 导出压缩（加密需付费插件） */
export interface ImportRequest {
  source_path: string
  target_dir: string
  archive_type?: 'zip' | 'tar.gz'
}

export interface ImportRecord {
  id: number
  tenant_id: number
  source_name: string
  archive_type: string
  target_dir: string
  extracted: boolean
  file_count: number
  status: string
  error?: string | null
  created_at?: string | null
}

export interface ExportRequest {
  source_dir: string
  target_name: string
  encrypted?: boolean
  password?: string | null
}

export interface ExportRecord {
  id: number
  tenant_id: number
  target_name: string
  encrypted: boolean
  plugin_required: boolean
  file_count: number
  status: string
  target_path?: string | null
  error?: string | null
  created_at?: string | null
}

export function createImport(payload: ImportRequest) {
  return request.post<any, ApiResponse<ImportRecord>>('/security/imports', payload)
}

export function fetchImports() {
  return request.get<any, ApiResponse<{ total: number; imports?: ImportRecord[]; items?: ImportRecord[] }>>('/security/imports')
}

export function createExport(payload: ExportRequest) {
  return request.post<any, ApiResponse<ExportRecord>>('/security/exports', payload)
}

export function fetchExports() {
  return request.get<any, ApiResponse<{ total: number; exports?: ExportRecord[]; items?: ExportRecord[] }>>('/security/exports')
}
