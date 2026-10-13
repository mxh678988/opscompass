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
