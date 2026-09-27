import request from './request'
import type { ApiResponse } from './metrics'

/** ---------------------------------------------------------------- 类型 */

export interface AiStatistics {
  analysis_total: number
  analysis_failed: number
  insight_total: number
  insight_pending: number
  action_total: number
  action_by_status: Record<string, number>
  insight_by_level: Record<string, number>
  ai_auto_executed: number
  human_pending: number
}

export interface AiConfigOut {
  enabled: boolean
  mode: string
  model: string
  base_url: string
  ready: boolean
  modes: Record<string, any>
  timeout: number
  max_tokens: number
  temperature: number
  probe?: Record<string, any> | null
  level_meta: Record<string, { name?: string; desc?: string }>
  statistics: AiStatistics
}

export interface LevelRule {
  id: number
  tenant_id: number
  code: string
  name: string
  object_type: string
  field: string
  operator: string
  threshold?: unknown[] | null
  level: string
  priority: number
  enabled: boolean
  builtin: boolean
  description?: string | null
}

export interface LevelRecord {
  id: number
  object_type: string
  object_id: number
  object_code: string
  level: string
  source: string
  rule_code?: string | null
  confidence?: number | null
  grader: string
  reason?: string | null
  graded_at?: string | null
  updated_at?: string | null
}

export interface AiGradeItem {
  object_id: number
  object_type?: string
  code: string
  level: string
  ai_level?: string
  rule_level?: string
  downgrade_blocked?: boolean
  confidence?: number | null
  reason?: string
  needs_human?: boolean
}

export interface GradeRunOut {
  rule_engine: {
    graded: number
    level_summary: Record<string, number>
    details: { object_type: string; code: string; level: string; reason: string }[]
  }
  ai?: {
    mode: string
    model: string
    applied: number
    duration_ms?: number
    items: AiGradeItem[]
  } | null
}

export interface Insight {
  id: number
  analysis_id?: number | null
  seq: number
  category: string
  severity: string
  title: string
  detail?: string | null
  metric_codes?: string[] | null
  evidence?: Record<string, { value?: number; delta_ratio?: number | null }> | null
  suggestion?: string | null
  action_type: string
  data_level: string
  confidence?: number | null
  status: string
  created_at?: string | null
}

export interface Analysis {
  id: number
  scope: string
  title: string
  mode: string
  model: string
  status: string
  granularity: string
  dim_key?: string | null
  result_summary?: string | null
  insight_count: number
  duration_ms: number
  prompt_tokens: number
  completion_tokens: number
  error?: string | null
  created_by: string
  created_at?: string | null
  finished_at?: string | null
}

export interface AnalysisRunOut {
  analysis: Analysis
  insights: Insight[]
  routing?: Record<string, number>
}

export interface ActionItem {
  id: number
  insight_id?: number | null
  analysis_id?: number | null
  policy_id?: number | null
  title: string
  action_type: string
  data_level: string
  severity: string
  handler: string
  status: string
  review_required: boolean
  assignee?: string | null
  decision_by?: string | null
  decision_at?: string | null
  decision_note?: string | null
  execution_result?: string | null
  executed_at?: string | null
  created_at?: string | null
}

export interface PolicyItem {
  id: number
  code: string
  name: string
  data_level: string
  actor: string
  action_type: string
  max_severity: string
  allow: boolean
  require_review: boolean
  require_approval: boolean
  priority: number
  enabled: boolean
  builtin: boolean
  description?: string | null
}

export interface PolicyDecide {
  data_level: string
  actor: string
  action_type: string
  severity: string
  allow: boolean
  require_review: boolean
  require_approval: boolean
  policy_code?: string | null
  policy_name?: string | null
  reason: string
}

export interface AuditItem {
  id: number
  actor_type: string
  actor: string
  action: string
  object_type: string
  object_id?: number | null
  from_state?: string | null
  to_state?: string | null
  detail?: string | null
  created_at?: string | null
}

/** ---------------------------------------------------------------- 配置与统计 */

export function fetchAiConfig(probe = false) {
  return request.get<any, ApiResponse<AiConfigOut>>('/ai/config', { params: { probe } })
}

export function fetchAiStatistics() {
  return request.get<any, ApiResponse<AiStatistics>>('/ai/statistics')
}

/** ---------------------------------------------------------------- 数据分级 */

export function fetchLevelRules() {
  return request.get<any, ApiResponse<LevelRule[]>>('/ai/level/rules')
}

export function seedLevelRules() {
  return request.post<any, ApiResponse<{ inserted: number; total: number }>>('/ai/level/rules/seed')
}

export function runGrade(payload: { object_types: string[]; use_ai: boolean; ai_limit: number }) {
  return request.post<any, ApiResponse<GradeRunOut>>('/ai/level/grade', payload)
}

export function fetchLevelRecords(params?: { object_type?: string; level?: string }) {
  return request.get<any, ApiResponse<LevelRecord[]>>('/ai/level/records', { params })
}

/** ---------------------------------------------------------------- AI 分析 */

export function runAnalysis(payload: {
  scope: string
  granularity: string
  dim_key?: string
  max_insights: number
  auto_route: boolean
  mode?: string
}) {
  return request.post<any, ApiResponse<AnalysisRunOut>>('/ai/analyze', payload)
}

export function fetchAnalyses(limit = 20) {
  return request.get<any, ApiResponse<Analysis[]>>('/ai/analyses', { params: { limit } })
}

export function fetchAnalysisInsights(analysisId: number) {
  return request.get<any, ApiResponse<Insight[]>>(`/ai/analyses/${analysisId}/insights`)
}

export function fetchInsights(params?: { status?: string; severity?: string; limit?: number }) {
  return request.get<any, ApiResponse<Insight[]>>('/ai/insights', { params })
}

export function routeInsights() {
  return request.post<any, ApiResponse<Record<string, number>>>('/ai/insights/route')
}

/** ---------------------------------------------------------------- 权限策略 */

export function fetchPolicies() {
  return request.get<any, ApiResponse<PolicyItem[]>>('/ai/policies')
}

export function seedPolicies() {
  return request.post<any, ApiResponse<{ inserted: number; total: number }>>('/ai/policies/seed')
}

export function updatePolicy(
  policyId: number,
  payload: Partial<Pick<PolicyItem, 'allow' | 'require_review' | 'require_approval' | 'enabled' | 'priority'>>,
) {
  return request.put<any, ApiResponse<PolicyItem>>(`/ai/policies/${policyId}`, payload)
}

export function decidePolicy(params: {
  data_level: string
  actor: string
  action_type: string
  severity: string
}) {
  return request.get<any, ApiResponse<PolicyDecide>>('/ai/policies/decide', { params })
}

/** ---------------------------------------------------------------- 处置与审计 */

export function fetchActions(params?: { status?: string; handler?: string; data_level?: string; limit?: number }) {
  return request.get<any, ApiResponse<ActionItem[]>>('/ai/actions', { params })
}

export function approveAction(actionId: number, payload: { operator: string; note?: string }) {
  return request.post<any, ApiResponse<ActionItem>>(`/ai/actions/${actionId}/approve`, payload)
}

export function rejectAction(actionId: number, payload: { operator: string; note?: string }) {
  return request.post<any, ApiResponse<ActionItem>>(`/ai/actions/${actionId}/reject`, payload)
}

export function executeAction(actionId: number, payload: { operator: string; note?: string; result?: string }) {
  return request.post<any, ApiResponse<ActionItem>>(`/ai/actions/${actionId}/execute`, payload)
}

export function fetchAudit(limit = 100) {
  return request.get<any, ApiResponse<AuditItem[]>>('/ai/audit', { params: { limit } })
}
