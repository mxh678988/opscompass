import request from './request'
import type { ApiResponse } from './metrics'

/** ============================== 类型定义 ============================== */

export interface LearningOverview {
  feedback_total: number
  adopt_count: number
  success_count: number
  adopt_rate: number
  success_rate: number
  avg_score: number
  top_weights: PolicyWeight[]
  weight_total: number
  case_total: number
  case_verified: number
  experiment_total: number
  experiment_running: number
}

export interface FeedbackItem {
  id: number
  tenant_id: number
  insight_id?: number | null
  action_item_id?: number | null
  policy_code?: string | null
  action_type?: string | null
  data_level?: string | null
  decision: string
  outcome: string
  outcome_score?: number | null
  effect_note?: string | null
  remark?: string | null
  recorded_by?: string | null
  applied: boolean
  applied_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface PolicyWeight {
  id: number
  policy_code: string
  action_type?: string | null
  policy_name?: string | null
  weight: number
  base_weight: number
  sample_count: number
  adopt_count: number
  success_count: number
  success_rate: number
  avg_score: number
  last_adjusted_at?: string | null
  adjust_note?: string | null
  updated_at?: string | null
}

export interface LearnCase {
  id: number
  case_no: string
  title: string
  category?: string | null
  tags: string[]
  scenario?: string | null
  action_taken?: string | null
  outcome?: string | null
  outcome_score?: number | null
  lesson?: string | null
  source_insight_id?: number | null
  source_feedback_id?: number | null
  status: string
  hit_count: number
  last_hit_at?: string | null
  created_by?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface LearnExperiment {
  id: number
  code: string
  name: string
  hypothesis?: string | null
  metric_code?: string | null
  status: string
  variant_a?: string | null
  variant_b?: string | null
  sample_a: number
  sample_b: number
  result_a: number
  result_b: number
  lift: number
  confidence: number
  winner?: string | null
  conclusion?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_by?: string | null
  created_at?: string | null
}

export interface Paged<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

export interface FeedbackPayload {
  insight_id?: number | null
  action_item_id?: number | null
  policy_code?: string
  action_type?: string
  data_level?: string
  decision?: string
  outcome?: string
  outcome_score?: number | null
  effect_note?: string
  remark?: string
  applied?: boolean
}

export interface CasePayload {
  title: string
  category?: string
  tags?: string[]
  scenario?: string
  action_taken?: string
  outcome?: string
  outcome_score?: number | null
  lesson?: string
  status?: string
}

export interface ExperimentPayload {
  name: string
  hypothesis?: string
  metric_code?: string
  variant_a?: string
  variant_b?: string
  status?: string
}

/** ============================== 总览 ============================== */

/** 学习进化总览：采纳率 / 成功率 / 权重 Top / 案例与实验计数 */
export function fetchLearningOverview() {
  return request.get<any, ApiResponse<LearningOverview>>('/learning/overview')
}

/** ============================== 决策反馈回流 ============================== */

/** 反馈列表（可按关键字 / 采纳结果 / 实际效果 / 策略编码过滤） */
export function fetchFeedbacks(params?: {
  keyword?: string
  decision?: string
  outcome?: string
  policy_code?: string
  page?: number
  size?: number
}) {
  return request.get<any, ApiResponse<Paged<FeedbackItem>>>('/learning/feedbacks', { params })
}

/** 登记一条决策反馈 */
export function createFeedback(payload: FeedbackPayload) {
  return request.post<any, ApiResponse<FeedbackItem>>('/learning/feedbacks', payload)
}

/** 补录 / 修正反馈的实际效果 */
export function patchFeedback(id: number, payload: Partial<FeedbackPayload>) {
  return request.patch<any, ApiResponse<FeedbackItem>>(`/learning/feedbacks/${id}`, payload)
}

/** 由反馈一键沉淀为经验案例 */
export function caseFromFeedback(payload: {
  feedback_id: number
  title?: string | null
  category?: string | null
  lesson?: string
  status?: string
}) {
  return request.post<any, ApiResponse<LearnCase>>('/learning/cases/from-feedback', payload)
}

/** ============================== 策略权重自调 ============================== */

/** 策略权重列表 */
export function fetchWeights(params?: { keyword?: string; page?: number; size?: number }) {
  return request.get<any, ApiResponse<Paged<PolicyWeight>>>('/learning/weights', { params })
}

/** 触发策略权重自调（policy_code 不传则全量重算） */
export function recomputeWeights(payload?: {
  policy_code?: string | null
  action_type?: string | null
  min_samples?: number
  learning_rate?: number
  weight_floor?: number
  weight_ceil?: number
  remark?: string
}) {
  return request.post<any, ApiResponse<{ updated: number; items: PolicyWeight[] }>>(
    '/learning/weights/recompute',
    payload ?? {},
  )
}

/** ============================== 经验案例库 ============================== */

/** 案例列表 */
export function fetchCases(params?: {
  keyword?: string
  category?: string
  status?: string
  page?: number
  size?: number
}) {
  return request.get<any, ApiResponse<Paged<LearnCase>>>('/learning/cases', { params })
}

/** 新建经验案例 */
export function createCase(payload: CasePayload) {
  return request.post<any, ApiResponse<LearnCase>>('/learning/cases', payload)
}

/** 修改经验案例 */
export function updateCase(id: number, payload: Partial<CasePayload>) {
  return request.patch<any, ApiResponse<LearnCase>>(`/learning/cases/${id}`, payload)
}

/** 标记案例被命中引用（累加命中次数） */
export function hitCase(id: number) {
  return request.post<any, ApiResponse<LearnCase>>(`/learning/cases/${id}/hit`)
}

/** 归档案例 */
export function archiveCase(id: number) {
  return request.post<any, ApiResponse<LearnCase>>(`/learning/cases/${id}/archive`)
}

/** ============================== A/B 对照实验 ============================== */

/** 实验列表 */
export function fetchExperiments(params?: {
  keyword?: string
  status?: string
  page?: number
  size?: number
}) {
  return request.get<any, ApiResponse<Paged<LearnExperiment>>>('/learning/experiments', { params })
}

/** 新建 A/B 对照实验 */
export function createExperiment(payload: ExperimentPayload) {
  return request.post<any, ApiResponse<LearnExperiment>>('/learning/experiments', payload)
}

/** 修改实验 */
export function updateExperiment(id: number, payload: Partial<ExperimentPayload>) {
  return request.patch<any, ApiResponse<LearnExperiment>>(`/learning/experiments/${id}`, payload)
}

/** 登记一次对照样本（variant: a / b） */
export function recordSample(id: number, payload: { variant: string; result: number; remark?: string }) {
  return request.post<any, ApiResponse<LearnExperiment>>(
    `/learning/experiments/${id}/samples`,
    payload,
  )
}

/** 结项并判定胜出方案（winner 不传则按 lift 自动判定） */
export function finishExperiment(
  id: number,
  payload?: { winner?: string | null; conclusion?: string; apply_weight?: boolean },
) {
  return request.post<any, ApiResponse<LearnExperiment>>(
    `/learning/experiments/${id}/finish`,
    payload ?? {},
  )
}

