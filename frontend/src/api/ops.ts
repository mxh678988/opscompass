import request from './request'
import type { ApiResponse } from './metrics'

/** ---------------------------------------------------------------- 类型 */

export interface Website {
  id: number
  tenant_id: number
  site_name: string
  site_url: string
  site_type: string
  theme: string
  status: string
  language: string
  description: string
  sitemap_generated: boolean
  seo_score: number
  geo_score: number
  ai_enabled: boolean
  ai_mode: string
  created_at?: string | null
  updated_at?: string | null
}

export interface WebsitePage {
  id: number
  tenant_id: number
  website_id: number
  title: string
  slug: string
  content: string
  seo_title: string
  seo_desc: string
  seo_keywords: string
  og_image: string
  publish_status: string
  published_at: string
  ai_enabled: boolean
  ai_generated: boolean
  content_level: string
  created_at?: string | null
  updated_at?: string | null
}

export interface ProductItem {
  id: number
  tenant_id: number
  website_id: number
  name: string
  slug: string
  price: number
  currency: string
  stock: number
  sku: string
  description: string
  status: string
  seo_title: string
  seo_desc: string
  ai_enabled: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface SeoTask {
  id: number
  tenant_id: number
  website_id: number
  task_type: string
  title: string
  description: string
  status: string
  result: string
  ai_model: string
  duration_ms: number
  ai_enabled: boolean
  created_at?: string | null
}

export interface GeoTask {
  id: number
  tenant_id: number
  website_id: number
  task_type: string
  title: string
  target_page_ids: string
  status: string
  result: string
  ai_model: string
  ai_enabled: boolean
  created_at?: string | null
}

export interface WebsiteAiConfig {
  id: number
  tenant_id: number
  website_id: number
  setting_type: string
  config_value: string
  enabled: boolean
  ai_model: string
  created_at?: string | null
  updated_at?: string | null
}

export interface MediaItem {
  id: number
  tenant_id: number
  website_id: number
  media_type: string
  file_url: string
  file_name: string
  file_size: number
  mime_type: string
  width: number
  height: number
  tags: string
  description: string
  folder: string
  usage_count: number
  content_level: string
  ai_generated: boolean
  created_at?: string | null
  updated_at?: string | null
}

/** ---------------------------------------------------------------- 网站/网店 */

export function createWebsite(payload: {
  site_name: string
  site_url: string
  site_type: string
  theme?: string
  status?: string
  language?: string
  description?: string
  ai_enabled?: boolean
  ai_mode?: string
}) {
  return request.post<any, ApiResponse<Website>>('/ops/websites', payload)
}

export function fetchWebsites(params?: { site_type?: string }) {
  return request.get<any, ApiResponse<Website[]>>('/ops/websites', { params })
}

export function fetchWebsite(websiteId: number) {
  return request.get<any, ApiResponse<Website>>(`/ops/websites/${websiteId}`)
}

export function updateWebsite(websiteId: number, payload: Partial<Website>) {
  return request.put<any, ApiResponse<Website>>(`/ops/websites/${websiteId}`, payload)
}

export function deleteWebsite(websiteId: number) {
  return request.delete<any, ApiResponse<{ id: number; deleted: boolean }>>(`/ops/websites/${websiteId}`)
}

/** ---------------------------------------------------------------- 页面/文章 */

export function createPage(
  websiteId: number,
  payload: {
    title: string
    slug?: string
    content?: string
    seo_title?: string
    seo_desc?: string
    seo_keywords?: string
    publish_status?: string
    ai_enabled?: boolean
    content_level?: string
  },
) {
  return request.post<any, ApiResponse<WebsitePage>>(`/ops/websites/${websiteId}/pages`, payload)
}

export function fetchPages(websiteId: number, params?: { publish_status?: string }) {
  return request.get<any, ApiResponse<WebsitePage[]>>(`/ops/websites/${websiteId}/pages`, { params })
}

export function updatePage(
  websiteId: number,
  pageId: number,
  payload: Partial<WebsitePage> & { title?: string },
) {
  return request.put<any, ApiResponse<WebsitePage>>(`/ops/websites/${websiteId}/pages/${pageId}`, payload)
}

export function deletePage(websiteId: number, pageId: number) {
  return request.delete<any, ApiResponse<{ id: number; deleted: boolean }>>(
    `/ops/websites/${websiteId}/pages/${pageId}`,
  )
}

/** ---------------------------------------------------------------- 商品 */

export function createProduct(
  websiteId: number,
  payload: {
    name: string
    price: number
    currency?: string
    stock?: number
    sku?: string
    description?: string
    status?: string
    seo_title?: string
    seo_desc?: string
    ai_enabled?: boolean
  },
) {
  return request.post<any, ApiResponse<ProductItem>>(`/ops/websites/${websiteId}/products`, payload)
}

export function fetchProducts(websiteId: number, params?: { status?: string }) {
  return request.get<any, ApiResponse<ProductItem[]>>(`/ops/websites/${websiteId}/products`, { params })
}

export function updateProduct(websiteId: number, productId: number, payload: Partial<ProductItem>) {
  return request.put<any, ApiResponse<ProductItem>>(
    `/ops/websites/${websiteId}/products/${productId}`,
    payload,
  )
}

export function deleteProduct(websiteId: number, productId: number) {
  return request.delete<any, ApiResponse<{ id: number; deleted: boolean }>>(
    `/ops/websites/${websiteId}/products/${productId}`,
  )
}

/** ---------------------------------------------------------------- SEO / GEO */

export function runSeoTask(
  websiteId: number,
  payload: { task_type: string; page_ids?: number[]; ai_enabled?: boolean; ai_model?: string },
) {
  return request.post<any, ApiResponse<SeoTask>>(`/ops/websites/${websiteId}/seo`, payload)
}

export function fetchSeoTasks(websiteId: number, params?: { status?: string }) {
  return request.get<any, ApiResponse<SeoTask[]>>(`/ops/websites/${websiteId}/seo`, { params })
}

export function runGeoTask(
  websiteId: number,
  payload: { task_type: string; page_ids?: number[]; ai_enabled?: boolean; ai_model?: string },
) {
  return request.post<any, ApiResponse<GeoTask>>(`/ops/websites/${websiteId}/geo`, payload)
}

export function fetchGeoTasks(websiteId: number, params?: { status?: string }) {
  return request.get<any, ApiResponse<GeoTask[]>>(`/ops/websites/${websiteId}/geo`, { params })
}

/** ---------------------------------------------------------------- AI 智能设置 */

export function saveAiConfig(
  websiteId: number,
  payload: { setting_type: string; config_value: Record<string, any>; enabled?: boolean; ai_model?: string },
) {
  return request.post<any, ApiResponse<WebsiteAiConfig>>(`/ops/websites/${websiteId}/ai-config`, payload)
}

export function fetchAiConfigs(websiteId: number, params?: { setting_type?: string }) {
  return request.get<any, ApiResponse<WebsiteAiConfig[]>>(`/ops/websites/${websiteId}/ai-config`, { params })
}

export function updateAiConfig(
  configId: number,
  payload: { setting_type: string; config_value?: Record<string, any>; enabled?: boolean; ai_model?: string },
) {
  return request.put<any, ApiResponse<WebsiteAiConfig>>(`/ops/ai-configs/${configId}`, payload)
}

/** ---------------------------------------------------------------- 媒体库 */

export function createMedia(
  websiteId: number,
  payload: {
    media_type: string
    file_url: string
    file_name?: string
    file_size?: number
    mime_type?: string
    width?: number
    height?: number
    description?: string
    tags?: string[]
    folder?: string
    content_level?: string
  },
) {
  return request.post<any, ApiResponse<MediaItem>>(`/ops/websites/${websiteId}/media`, payload)
}

export function fetchMedia(
  websiteId: number,
  params?: { media_type?: string; folder?: string },
) {
  return request.get<any, ApiResponse<MediaItem[]>>(`/ops/websites/${websiteId}/media`, { params })
}

export function updateMedia(websiteId: number, mediaId: number, payload: Record<string, any>) {
  return request.put<any, ApiResponse<MediaItem>>(`/ops/websites/${websiteId}/media/${mediaId}`, payload)
}

export function deleteMedia(websiteId: number, mediaId: number) {
  return request.delete<any, ApiResponse<{ id: number; deleted: boolean }>>(
    `/ops/websites/${websiteId}/media/${mediaId}`,
  )
}

/** ---------------------------------------------------------------- 自媒体 */

export function createSocialPost(
  websiteId: number,
  payload: {
    platform: string
    content: string
    media_ids?: number[]
    scheduled_at?: string
    ai_enabled?: boolean
    ai_model?: string
  },
) {
  return request.post<any, ApiResponse<Record<string, any>>>(`/ops/websites/${websiteId}/social`, payload)
}

export function optimizeSocial(
  websiteId: number,
  payload: { platform: string; content: string; tone: string; mode?: string },
) {
  return request.post<any, ApiResponse<Record<string, any>>>(
    `/ops/websites/${websiteId}/social/optimize`,
    payload,
  )
}

export function scheduleSocial(
  websiteId: number,
  payload: { platform: string; posts: Array<{ title?: string; content?: string; scheduled_at?: string }> },
) {
  return request.post<any, ApiResponse<Record<string, any>>>(
    `/ops/websites/${websiteId}/social/schedule`,
    payload,
  )
}

export function analyzeSocial(websiteId: number, payload: { platform: string }) {
  return request.post<any, ApiResponse<Record<string, any>>>(
    `/ops/websites/${websiteId}/social/analytics`,
    payload,
  )
}

/** ---------------------------------------------------------------- AI 运营分析 */

export function runOpsAnalysis(payload: {
  scope: string
  website_id: number
  page_ids?: number[]
  max_insights?: number
  mode?: string
}) {
  return request.post<any, ApiResponse<Record<string, any>>>('/ops/ai/analyze', payload)
}

export function generateContent(payload: {
  website_id: number
  page_id: number
  content_type?: string
  keywords?: string[]
  tone?: string
  mode?: string
}) {
  return request.post<any, ApiResponse<Record<string, any>>>('/ops/ai/generate-content', payload)
}

/** ---------------------------------------------------------------- 站内预览（P3 内置浏览器） */

export interface CrawlDiagnostic {
  level: string
  item: string
  message: string
}

export interface CrawlResult {
  url: string
  final_url: string
  status_code: number
  elapsed_ms: number
  content_type: string
  bytes: number
  title: string
  meta_description: string
  h1: string[]
  h2_count: number
  word_count: number
  canonical: string
  og_title: string
  text_preview: string
  diagnostics: CrawlDiagnostic[]
}

/** 抓取本站同域页面并返回 SEO 体检结果（仅同域、禁内网、限时限量） */
export function crawlSitePage(websiteId: number, payload: { page_id?: number; path?: string }) {
  return request.post<any, ApiResponse<CrawlResult>>(`/ops/websites/${websiteId}/crawl`, payload)
}
