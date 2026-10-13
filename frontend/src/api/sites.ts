import request from './request'
import type { ApiResponse } from './metrics'

/** M15/M16 响应式网站生成器 + 网站资源管理器 */
export interface SiteSection {
  type: string
  title?: string | null
  text?: string | null
  items?: Array<Record<string, unknown>>
}

export interface SiteContent {
  sections?: SiteSection[]
}

export interface SiteProjectIn {
  name: string
  slug: string
  description?: string | null
  template?: string
  seo_title?: string | null
  seo_description?: string | null
  seo_keywords?: string | null
  geo_enabled?: boolean
  geo_region?: string | null
  geo_org_type?: string | null
  host_mode?: 'link' | 'space'
  content?: SiteContent | null
}

export interface SiteProject {
  id: number
  tenant_id: number
  name: string
  slug: string
  description?: string | null
  template: string
  seo_title?: string | null
  seo_description?: string | null
  seo_keywords?: string | null
  geo_enabled: boolean
  geo_region?: string | null
  geo_org_type?: string | null
  host_mode: string
  status: string
  content?: unknown
  publish_path?: string | null
  created_at?: string
  updated_at?: string
}

export interface SiteResourceIn {
  resource_type: string
  name: string
  path: string
  size_bytes?: number
  checksum?: string | null
  meta?: Record<string, unknown> | null
}

export interface SiteResource {
  id: number
  tenant_id: number
  project_id?: number | null
  resource_type: string
  name: string
  path: string
  size_bytes: number
  checksum?: string | null
  status: string
  meta?: unknown
  created_at?: string
  updated_at?: string
}

export interface ResourceScanOut {
  project_id: number
  scanned: number
  created: number
  updated: number
  marked_missing: number
}

export interface ResourceSummaryOut {
  project_id: number
  total: number
  total_size_bytes: number
  by_type: Record<string, number>
  by_status: Record<string, number>
}

export function fetchSites() {
  return request.get<any, ApiResponse<SiteProject[]>>('/sites')
}

export function createSite(payload: SiteProjectIn) {
  return request.post<any, ApiResponse<SiteProject>>('/sites', payload)
}

export function fetchSite(siteId: number) {
  return request.get<any, ApiResponse<SiteProject>>(`/sites/${siteId}`)
}

export function patchSite(siteId: number, payload: Partial<SiteProjectIn>) {
  return request.patch<any, ApiResponse<SiteProject>>(`/sites/${siteId}`, payload)
}

export function deleteSite(siteId: number) {
  return request.delete<any, ApiResponse<Record<string, unknown>>>(`/sites/${siteId}`)
}

export function publishSite(siteId: number) {
  return request.post<any, ApiResponse<SiteProject>>(`/sites/${siteId}/publish`)
}

/** 返回 HTML 文档字符串（Response content-type: text/html） */
export function previewSite(siteId: number) {
  return request.get<any, string>(`/sites/${siteId}/preview`)
}

export function scanSiteResources(siteId: number) {
  return request.post<any, ApiResponse<ResourceScanOut>>(`/sites/${siteId}/resources/scan`)
}

export function fetchSiteResources(siteId: number, params?: { resource_type?: string; status?: string; keyword?: string }) {
  return request.get<any, ApiResponse<SiteResource[]>>(`/sites/${siteId}/resources`, { params })
}

export function fetchResourceSummary(siteId: number) {
  return request.get<any, ApiResponse<ResourceSummaryOut>>(`/sites/${siteId}/resources/summary`)
}

export function patchSiteResource(resourceId: number, payload: { name?: string; resource_type?: string; status?: string; meta?: Record<string, unknown> | null }) {
  return request.patch<any, ApiResponse<SiteResource>>(`/sites/resources/${resourceId}`, payload)
}

export function deleteSiteResource(resourceId: number) {
  return request.delete<any, ApiResponse<Record<string, unknown>>>(`/sites/resources/${resourceId}`)
}
