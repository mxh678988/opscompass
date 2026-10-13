import request from './request'
import type { ApiResponse, PageResult } from './metrics'

/** M11 知识库：经验/SOP/洞察沉淀，供 Agent 检索引用 */
export interface KnowledgeDocIn {
  title: string
  doc_type: string
  status?: string
  content?: string | null
  summary?: string | null
  tags?: string[]
  scenario?: string | null
  source?: string
  author?: string
}

export interface KnowledgeDoc {
  id: number
  tenant_id: number
  title: string
  doc_type: string
  status: string
  content?: string | null
  summary?: string | null
  tags?: string[] | null
  scenario?: string | null
  source?: string
  ref_count: number
  author?: string | null
  published_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface KnowledgeRefIn {
  doc_ids: number[]
  source?: string
  ref_key?: string | null
  note?: string | null
}

export function createKnowledgeDoc(payload: KnowledgeDocIn) {
  return request.post<any, ApiResponse<KnowledgeDoc>>('/knowledge/docs', payload)
}

export function fetchKnowledgeDocs(params?: {
  keyword?: string
  doc_type?: string
  status?: string
  scenario?: string
  page?: number
  size?: number
}) {
  return request.get<any, ApiResponse<PageResult<KnowledgeDoc>>>('/knowledge/docs', { params })
}

export function fetchKnowledgeDoc(docId: number) {
  return request.get<any, ApiResponse<KnowledgeDoc>>(`/knowledge/docs/${docId}`)
}

export function patchKnowledgeDoc(docId: number, payload: { title?: string; doc_type?: string; status?: string; summary?: string; content?: string; tags?: string[]; scenario?: string }) {
  return request.patch<any, ApiResponse<KnowledgeDoc>>(`/knowledge/docs/${docId}`, payload)
}

export function deleteKnowledgeDoc(docId: number) {
  return request.delete<any, ApiResponse<Record<string, unknown>>>(`/knowledge/docs/${docId}`)
}

export function searchKnowledgeDocs(params: { keyword: string; doc_type?: string; scenario?: string; limit?: number }) {
  return request.get<any, ApiResponse<{ total: number; limit: number; items: KnowledgeDoc[] }>>('/knowledge/search', { params })
}

export function registerKnowledgeRefs(payload: KnowledgeRefIn) {
  return request.post<any, ApiResponse<Record<string, unknown>>>('/knowledge/refs', payload)
}

/* ---------- 知识库（KnowledgeBase）：管理 / 文件 / 问答 ---------- */

export interface KnowledgeBaseIn {
  name: string
  description?: string | null
  config?: Record<string, unknown> | null
}

export interface KnowledgeBasePatch {
  name?: string
  description?: string | null
  config?: Record<string, unknown> | null
  status?: string
}

export interface KnowledgeBaseItem {
  id: number
  tenant_id: number
  name: string
  description?: string | null
  config?: Record<string, unknown> | null
  status: string
  created_at?: string | null
  updated_at?: string | null
  doc_count?: number
  file_count?: number
  files?: KnowledgeBaseFile[]
}

export interface KnowledgeBaseFile {
  id: number
  base_id: number
  file_name: string
  file_type: string
  size_bytes: number
  uploader?: string
  status?: string
  created_at?: string | null
}

export interface KnowledgeAskIn {
  question: string
  top_k?: number
}

export interface KnowledgeAskOut {
  answer: string
  fallback: boolean
  model?: string | null
  sources: { title: string; kind: string; content: string }[]
}

export function createKnowledgeBase(payload: KnowledgeBaseIn) {
  return request.post<any, ApiResponse<KnowledgeBaseItem>>('/knowledge/bases', payload)
}

export function fetchKnowledgeBases(params?: { keyword?: string; status?: string }) {
  return request.get<any, ApiResponse<KnowledgeBaseItem[]>>('/knowledge/bases', { params })
}

export function fetchKnowledgeBase(baseId: number) {
  return request.get<any, ApiResponse<KnowledgeBaseItem>>(`/knowledge/bases/${baseId}`)
}

export function patchKnowledgeBase(baseId: number, payload: KnowledgeBasePatch) {
  return request.patch<any, ApiResponse<KnowledgeBaseItem>>(`/knowledge/bases/${baseId}`, payload)
}

export function deleteKnowledgeBase(baseId: number) {
  return request.delete<any, ApiResponse<Record<string, unknown>>>(`/knowledge/bases/${baseId}`)
}

export function uploadKnowledgeBaseFile(baseId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  return request.post<any, ApiResponse<KnowledgeBaseFile>>(`/knowledge/bases/${baseId}/files`, form)
}

export function fetchKnowledgeBaseFiles(baseId: number) {
  return request.get<any, ApiResponse<KnowledgeBaseFile[]>>(`/knowledge/bases/${baseId}/files`)
}

export function deleteKnowledgeBaseFile(fileId: number, baseId: number) {
  return request.delete<any, ApiResponse<Record<string, unknown>>>('/knowledge/files/' + fileId, { params: { base_id: baseId } })
}

export function askKnowledgeBase(baseId: number, payload: KnowledgeAskIn) {
  return request.post<any, ApiResponse<KnowledgeAskOut>>(`/knowledge/bases/${baseId}/ask`, payload)
}
