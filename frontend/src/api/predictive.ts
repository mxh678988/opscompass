import request from './request'
import type { ApiResponse, PageResult } from './metrics'

/** M9 预测引擎：流失/转化概率预测（本地优先、规则兜底） */
export interface PredictionRunIn {
  name: string
  target?: 'churn' | 'conversion'
  subject_keys?: string[]
  features?: Record<string, unknown>
  mode?: 'local' | 'api' | 'rule'
  threshold?: number
  rule_fallback?: boolean
  source?: string
}

export interface PredictionBatchIn {
  target: 'churn' | 'conversion'
  subjects: Array<{ key: string; name?: string; features?: Record<string, unknown> }>
  mode?: 'local' | 'api' | 'rule'
  threshold?: number
  rule_fallback?: boolean
}

export interface PredictionResultItem {
  id: number
  job_id: number
  target: string
  subject_key: string
  subject_name?: string | null
  probability: number
  band: string
  mode: string
  model?: string | null
  confidence?: number | null
  features?: unknown
  reasons?: unknown
  created_at?: string | null
}

export interface PredictionJob {
  id: number
  tenant_id: number
  name: string
  target: string
  status: string
  mode: string
  model?: string | null
  source?: string
  feature_count: number
  subject_count: number
  threshold?: number | null
  rule_fallback_used: boolean
  error?: string | null
  created_by?: string
  created_at?: string | null
  finished_at?: string | null
  results?: PredictionResultItem[]
}

export function createPredictionRun(payload: PredictionRunIn) {
  return request.post<any, ApiResponse<PredictionJob>>('/predictive/runs', payload)
}

export function createPredictionBatch(payload: PredictionBatchIn) {
  return request.post<any, ApiResponse<PredictionJob>>('/predictive/batch', payload)
}

export function fetchPredictionRuns(params?: {
  keyword?: string
  target?: string
  status?: string
  page?: number
  size?: number
}) {
  return request.get<any, ApiResponse<PageResult<PredictionJob>>>('/predictive/runs', { params })
}

export function fetchPredictionRun(jobId: number) {
  return request.get<any, ApiResponse<PredictionJob>>(`/predictive/runs/${jobId}`)
}
