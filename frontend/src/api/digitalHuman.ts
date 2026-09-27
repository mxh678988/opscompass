import request from './request'
import type { ApiResponse } from './metrics'

/** ============================== 类型定义 ============================== */

export interface DhEngineStage {
  engine: string
  ready: boolean
  detail?: string
  endpoint?: string
}

export interface DhEngineStatus {
  script: DhEngineStage
  voice: DhEngineStage
  avatar: DhEngineStage
  compose: DhEngineStage
}

export interface DhAvatar {
  id: number
  tenant_id: number
  name: string
  avatar_type: string
  gender: string
  style: string
  preview_url: string
  source_url: string
  engine: string
  status: string
  remark: string
  created_at?: string | null
  updated_at?: string | null
}

export interface DhVoice {
  id: number
  tenant_id: number
  name: string
  engine: string
  voice_id: string
  language: string
  gender: string
  speed: string
  sample_url: string
  status: string
  remark: string
  created_at?: string | null
  updated_at?: string | null
}

export interface DhSegment {
  index?: number
  title?: string
  content?: string
  seconds?: number
}

export interface DhTask {
  id: number
  project_id: number
  stage: string
  stage_name: string
  seq: number
  status: string
  progress: number
  engine: string
  input_brief: string
  output_url: string
  output_text: string
  message: string
  duration_ms?: number | null
  started_at?: string | null
  finished_at?: string | null
}

export interface DhProject {
  id: number
  tenant_id: number
  name: string
  topic: string
  source_text: string
  script: string
  segments: DhSegment[]
  avatar_id?: number | null
  voice_id?: number | null
  workflow_id?: number | null
  resolution: string
  aspect_ratio: string
  duration_sec: number
  subtitle_enabled: boolean
  bgm: string
  status: string
  progress: number
  video_url: string
  audio_url: string
  cover_url: string
  simulated: boolean
  ai_model: string
  error: string
  remark: string
  created_at?: string | null
  updated_at?: string | null
  tasks?: DhTask[]
}

export interface WorkflowStep {
  stage: string
  name: string
  engine: string
  enabled: boolean
}

export interface DhWorkflow {
  id: number
  tenant_id: number
  name: string
  description: string
  steps: WorkflowStep[]
  is_default: boolean
  enabled: boolean
  run_count: number
  created_at?: string | null
  updated_at?: string | null
}

export interface Paged<T> {
  total: number
  page: number
  size: number
  items: T[]
}

export interface DhOverview {
  avatars: number
  voices: number
  workflows: number
  projects: number
  done: number
  rendering: number
  failed: number
  simulated: number
  total_duration_sec: number
  avg_duration_sec: number
  success_rate: number
  recent_projects: DhProject[]
  engine_status: DhEngineStatus
  stages: { stage: string; name: string }[]
}

export interface DhGenerateResult {
  project: DhProject
  ok: boolean
  simulated?: boolean
  engine_status?: DhEngineStatus
  message?: string
  steps?: string[]
}

export interface DhScriptResult {
  project: DhProject
  script: string
  segments: DhSegment[]
  ai_model: string
  simulated: boolean
  message?: string
}

export interface DeletedOut {
  id: number
  deleted: boolean
}

/** ============================== 接口定义 ============================== */

/** 数字人总览（计数、成功率、引擎状态、近期项目） */
export function fetchOverview() {
  return request.get<any, ApiResponse<DhOverview>>('/digital-human/overview')
}

/** 四阶段引擎可用性探测 */
export function fetchEngines() {
  return request.get<any, ApiResponse<DhEngineStatus>>('/digital-human/engines')
}

/** ---------------- 形象库 ---------------- */

export function fetchAvatars(
  params: { keyword?: string; avatar_type?: string; page?: number; size?: number } = {},
) {
  return request.get<any, ApiResponse<Paged<DhAvatar>>>('/digital-human/avatars', { params })
}

export function createAvatar(payload: Partial<DhAvatar>) {
  return request.post<any, ApiResponse<DhAvatar>>('/digital-human/avatars', payload)
}

export function updateAvatar(id: number, payload: Partial<DhAvatar>) {
  return request.patch<any, ApiResponse<DhAvatar>>(`/digital-human/avatars/${id}`, payload)
}

export function deleteAvatar(id: number) {
  return request.delete<any, ApiResponse<DeletedOut>>(`/digital-human/avatars/${id}`)
}

/** ---------------- 音色库 ---------------- */

export function fetchVoices(
  params: { keyword?: string; engine?: string; page?: number; size?: number } = {},
) {
  return request.get<any, ApiResponse<Paged<DhVoice>>>('/digital-human/voices', { params })
}

export function createVoice(payload: Partial<DhVoice>) {
  return request.post<any, ApiResponse<DhVoice>>('/digital-human/voices', payload)
}

export function updateVoice(id: number, payload: Partial<DhVoice>) {
  return request.patch<any, ApiResponse<DhVoice>>(`/digital-human/voices/${id}`, payload)
}

export function deleteVoice(id: number) {
  return request.delete<any, ApiResponse<DeletedOut>>(`/digital-human/voices/${id}`)
}

/** ---------------- 生成项目 ---------------- */

export function fetchProjects(
  params: { keyword?: string; status?: string; page?: number; size?: number } = {},
) {
  return request.get<any, ApiResponse<Paged<DhProject>>>('/digital-human/projects', { params })
}

export function createProject(payload: Record<string, unknown>) {
  return request.post<any, ApiResponse<DhProject>>('/digital-human/projects', payload)
}

export function fetchProject(id: number) {
  return request.get<any, ApiResponse<DhProject>>(`/digital-human/projects/${id}`)
}

export function updateProject(id: number, payload: Record<string, unknown>) {
  return request.patch<any, ApiResponse<DhProject>>(`/digital-human/projects/${id}`, payload)
}

export function deleteProject(id: number) {
  return request.delete<any, ApiResponse<DeletedOut>>(`/digital-human/projects/${id}`)
}

/** 生成 / 重写口播稿（含分镜） */
export function generateScript(
  id: number,
  payload: {
    tone?: string
    segment_count?: number
    target_sec?: number
    style?: string
    keywords?: string[]
    rewrite?: boolean
  },
) {
  return request.post<any, ApiResponse<DhScriptResult>>(`/digital-human/projects/${id}/script`, payload)
}

/** 一键生成：脚本 -> 配音 -> 数字人驱动 -> 成片合成 */
export function runGenerate(
  id: number,
  payload: { force?: boolean; skip_script?: boolean; engine_preference?: Record<string, string>; remark?: string } = {},
) {
  return request.post<any, ApiResponse<DhGenerateResult>>(`/digital-human/projects/${id}/generate`, payload)
}

/** ---------------- 工作流模板 ---------------- */

export function fetchWorkflows(params: { page?: number; size?: number } = {}) {
  return request.get<any, ApiResponse<Paged<DhWorkflow>>>('/digital-human/workflows', { params })
}

export function createWorkflow(payload: {
  name: string
  description?: string
  steps?: WorkflowStep[]
  enabled?: boolean
}) {
  return request.post<any, ApiResponse<DhWorkflow>>('/digital-human/workflows', payload)
}

export function updateWorkflow(
  id: number,
  payload: { name?: string; description?: string; steps?: WorkflowStep[]; enabled?: boolean },
) {
  return request.patch<any, ApiResponse<DhWorkflow>>(`/digital-human/workflows/${id}`, payload)
}

export function deleteWorkflow(id: number) {
  return request.delete<any, ApiResponse<DeletedOut>>(`/digital-human/workflows/${id}`)
}

/** 按指定工作流模板执行一键生成 */
export function runWorkflow(id: number, payload: { project_id: number; engine_preference?: Record<string, string> }) {
  return request.post<any, ApiResponse<DhGenerateResult>>(`/digital-human/workflows/${id}/run`, payload)
}
