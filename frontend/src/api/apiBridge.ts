import request from './request'
import type { ApiResponse } from './metrics'

/** M13 API 代申请助手：平台模板 + 申请任务跟踪（凭据服务端加密） */
export interface ApiPlatformTemplateIn {
  name: string
  apply_url: string
  field_schema?: Record<string, unknown>
  requires_manual?: boolean
  category?: string
  enabled?: boolean
}

export interface ApiPlatformTemplate {
  id: number
  name: string
  apply_url: string
  field_schema?: unknown
  requires_manual?: boolean
  category?: string
  enabled?: boolean
  created_at?: string | null
}

export interface ApiApplyTaskIn {
  platform_id?: number | null
  platform?: string
  account?: string
  password?: string
  remark?: string | null
  created_by?: string
}

export interface ApiApplyTaskPatch {
  status?: string
  progress?: number
  result_message?: string | null
  error?: string | null
}

export interface ApiApplyTask {
  id: number
  platform_id?: number | null
  platform?: string
  account?: string
  status?: string
  progress?: number
  result_message?: string | null
  error?: string | null
  remark?: string | null
  created_by?: string
  created_at?: string | null
}

export function createApiTemplate(payload: ApiPlatformTemplateIn) {
  return request.post<any, ApiResponse<Record<string, unknown>>>('/api-bridge/templates', payload)
}

export function patchApiTemplate(templateId: number, payload: Partial<ApiPlatformTemplateIn>) {
  return request.patch<any, ApiResponse<Record<string, unknown>>>(`/api-bridge/templates/${templateId}`, payload)
}

export function fetchApiTemplates(params?: { category?: string; enabled?: boolean; keyword?: string; page?: number; size?: number }) {
  return request.get<any, ApiResponse<Record<string, unknown>>>('/api-bridge/templates', { params })
}

export function fetchApiTemplate(templateId: number) {
  return request.get<any, ApiResponse<Record<string, unknown>>>(`/api-bridge/templates/${templateId}`)
}

export function deleteApiTemplate(templateId: number) {
  return request.delete<any, ApiResponse<Record<string, unknown>>>(`/api-bridge/templates/${templateId}`)
}

export function createApiTask(payload: ApiApplyTaskIn) {
  return request.post<any, ApiResponse<Record<string, unknown>>>('/api-bridge/tasks', payload)
}

export function patchApiTask(taskId: number, payload: ApiApplyTaskPatch) {
  return request.patch<any, ApiResponse<Record<string, unknown>>>(`/api-bridge/tasks/${taskId}`, payload)
}

export function fetchApiTasks(params?: { status?: string; keyword?: string; page?: number; size?: number }) {
  return request.get<any, ApiResponse<Record<string, unknown>>>('/api-bridge/tasks', { params })
}

export function fetchApiTask(taskId: number) {
  return request.get<any, ApiResponse<Record<string, unknown>>>(`/api-bridge/tasks/${taskId}`)
}
