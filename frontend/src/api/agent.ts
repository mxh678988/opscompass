import request from './request'
import type { ApiResponse, PageResult } from './metrics'

/** M12 智能体编排：场景模板 -> 洞察分析 -> 人工审批 -> 动作执行 */
export interface AgentRunIn {
  name: string
  scenario?: string
  datasource_bindings?: Record<string, unknown>
  action_config?: Record<string, unknown>
  approval_required?: boolean
  created_by?: string
}

export interface AgentRunPatch {
  status?: string
  approve_note?: string | null
  approved_by?: string
}

export interface AgentActionIn {
  insight_id?: number | null
  action_type?: string
  payload?: Record<string, unknown>
}

export interface AgentInsight {
  id: number
  run_id: number
  seq: number
  title: string
  detail?: string | null
  severity: string
  evidence?: unknown
  suggestion?: string | null
  suggested_action_type?: string | null
  status: string
  created_at?: string | null
}

export interface AgentAction {
  id: number
  run_id: number
  insight_id?: number | null
  action_type: string
  payload?: unknown
  status?: string
  created_at?: string | null
}

export interface AgentRun {
  id: number
  tenant_id: number
  name: string
  scenario: string
  status: string
  datasource_bindings?: unknown
  knowledge_refs?: unknown
  action_config?: unknown
  insight_agent?: string
  action_agent?: string
  approval_required: boolean
  approved_by?: string | null
  approved_at?: string | null
  approve_note?: string | null
  result_summary?: string | null
  result_published?: boolean
  result_event_id?: string | null
  error?: string | null
  created_by?: string
  created_at?: string | null
  finished_at?: string | null
  insights?: AgentInsight[]
  actions?: AgentAction[]
}

export function createAgentRun(payload: AgentRunIn) {
  return request.post<any, ApiResponse<AgentRun>>('/agents/runs', payload)
}

export function fetchAgentRuns(params?: {
  status?: string
  scenario?: string
  keyword?: string
  page?: number
  size?: number
}) {
  return request.get<any, ApiResponse<PageResult<AgentRun>>>('/agents/runs', { params })
}

export function fetchAgentRun(runId: number) {
  return request.get<any, ApiResponse<AgentRun>>(`/agents/runs/${runId}`)
}

export function analyzeAgentRun(runId: number) {
  return request.post<any, ApiResponse<AgentRun>>(`/agents/runs/${runId}/analyze`)
}

export function patchAgentRun(runId: number, payload: AgentRunPatch) {
  return request.patch<any, ApiResponse<AgentRun>>(`/agents/runs/${runId}`, payload)
}

export function registerAgentAction(runId: number, payload: AgentActionIn) {
  return request.post<any, ApiResponse<AgentAction>>(`/agents/runs/${runId}/actions`, payload)
}

export function completeAgentRun(runId: number) {
  return request.post<any, ApiResponse<AgentRun>>(`/agents/runs/${runId}/complete`)
}

export function failAgentRun(runId: number) {
  return request.post<any, ApiResponse<AgentRun>>(`/agents/runs/${runId}/fail`)
}
