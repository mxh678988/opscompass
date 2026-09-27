import request from './request'
import type { ApiResponse } from './metrics'

/** ---------------------------------------------------------------- 类型 */

/** 单类存储引擎能力 */
export interface EngineCapability {
  kind: string
  engine: string
  label: string
  available: boolean
  degraded: boolean
  detail?: Record<string, any>
}

/** 存储适配层总览 */
export interface StorageOverview {
  healthy: boolean
  storage_routing_enabled: boolean
  cache_enabled: boolean
  capabilities: EngineCapability[]
  stats?: Record<string, any>
  /** 路由规则概览（后端一并返回，便于单次请求渲染） */
  routing?: RoutingRules
  /** 内置样例识别结果 */
  examples?: IdentifyResult[]
}

/** 路由规则 */
export interface RouteRule {
  id: number
  name: string
  match_field: string
  match_value: string
  data_kind: string
  engine: string
  priority: number
  enabled: boolean
  tenant_id?: number | null
}

/** 路由规则集合 */
export interface RoutingRules {
  routing_enabled: boolean
  rule_count: number
  custom_rule_count: number
  by_kind: Record<string, number>
  kinds: { data_kind: string; engine: string; label: string }[]
  rules: RouteRule[]
}

/** 识别结果 */
export interface IdentifyResult {
  data_kind: string
  engine: string
  label: string
  matched: boolean
  reason: string
  rule_id?: number | null
  /** 本次识别输入 */
  inputs?: Record<string, any>
}

/** 全文检索命中 */
export interface SearchHit {
  id: number
  doc_type: string
  doc_id: string
  title: string
  content?: string | null
  keywords?: string | null
  url?: string | null
  rank: number
}

/** 全文检索结果 */
export interface SearchOut {
  query: string
  doc_type?: string | null
  total: number
  items: SearchHit[]
  engine: string
  /** pg_trgm 扩展是否可用 */
  pg_trgm?: boolean
  /** 降级说明（不可用时给出） */
  note?: string | null
}

/** 单范围对账结果 */
export interface ConsistencyItem {
  scope: string
  status: string
  checked: number
  matched: number
  missing?: number
  extra?: number
  mismatched?: number
  repaired?: number
  /** 索引清理条数（search_index 范围） */
  pruned?: number
  auto_repair?: boolean
  errors?: string[]
  /** 差异样例（missing / extra / mismatched） */
  samples?: Record<string, any>
  detail?: Record<string, any>
}

/** 对账总结果 */
export interface ConsistencyRun {
  overall: string
  scopes: string[]
  auto_repair: boolean
  elapsed_ms: number
  checked: number
  matched: number
  repaired: number
  pruned: number
  results: ConsistencyItem[]
}

/** 对账历史记录 */
export interface ConsistencyRecord {
  id: number
  scope: string
  status: string
  checked: number
  matched: number
  missing?: number
  extra?: number
  mismatched?: number
  repaired?: number
  auto_repair: boolean
  operator?: string | null
  created_at?: string | null
}

/** ---------------------------------------------------------------- 接口 */

/** 存储适配层总览：引擎能力矩阵 + 规模统计 */
export function fetchStorageOverview() {
  return request.get<any, ApiResponse<StorageOverview>>('/storage/overview')
}

/** 幂等初始化：受管目录 + 内置规则 + 时序分区 */
export function bootstrapStorage() {
  return request.post<any, ApiResponse<any>>('/storage/bootstrap', {})
}

/** 路由规则列表 */
export function fetchRoutingRules() {
  return request.get<any, ApiResponse<RoutingRules>>('/storage/routing/rules')
}

/** 识别数据类型并给出目标存储引擎 */
export function identifyRoute(payload: { ds_type?: string; file_ext?: string; content?: string }) {
  return request.post<any, ApiResponse<IdentifyResult>>('/storage/routing/identify', payload)
}

/** 全文检索 */
export function searchDocuments(params: { q: string; doc_type?: string; limit?: number }) {
  return request.get<any, ApiResponse<SearchOut>>('/storage/search', { params })
}

/** 重建全文索引 */
export function reindexDocuments(scope?: string[]) {
  return request.post<any, ApiResponse<any>>('/storage/search/reindex', { scope })
}

/** 回填存量指标值到时序分区表 */
export function backfillTimeseries(batchSize?: number) {
  return request.post<any, ApiResponse<any>>('/storage/backfill', {}, { params: { batch_size: batchSize } })
}

/** 执行跨存储一致性对账 */
export function runConsistency(payload: { scopes?: string[]; auto_repair?: boolean } = {}) {
  return request.post<any, ApiResponse<ConsistencyRun>>('/storage/consistency/run', payload)
}

/** 最近对账记录 */
export function fetchRecentConsistency(limit = 10) {
  return request.get<any, ApiResponse<ConsistencyRecord[]>>('/storage/consistency/recent', {
    params: { limit },
  })
}
