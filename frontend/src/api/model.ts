import request from './request'
import type { ApiResponse } from './metrics'

/** ============================== 硬件探测 ============================== */

export interface HardwareCpu {
  model?: string | null
  physical_cores?: number | null
  logical_cores?: number | null
  freq_mhz?: number | null
  socket_count?: number | null
  source?: string | null
  warnings?: string[]
}

export interface HardwareMemory {
  total_mb?: number | null
  available_mb?: number | null
  used_percent?: number | null
  source?: string | null
  warnings?: string[]
}

export interface HardwareDisk {
  mount?: string | null
  total_gb?: number | null
  free_gb?: number | null
  used_percent?: number | null
  source?: string | null
}

export interface HardwareGpu {
  name?: string | null
  vendor?: string | null
  vram_total_mb?: number | null
  vram_free_mb?: number | null
  vram_accurate?: boolean
  driver?: string | null
  source?: string | null
  warnings?: string[]
}

export interface HardwareVram {
  total_mb?: number | null
  total_gb?: number | null
  accurate?: boolean | null
  vendors?: string[]
}

export interface NetworkTarget {
  label: string
  url?: string | null
  host?: string | null
  port?: number | null
  reachable: boolean
  latency_ms?: number | null
  message?: string | null
}

export interface HardwareNetwork {
  hostname?: string | null
  interfaces?: Record<string, unknown>[]
  egress_ip?: string | null
  dns_ok?: boolean | null
  tcp_ok?: boolean | null
  latency_ms?: number | null
  targets?: NetworkTarget[]
  sources?: string[]
  warnings?: string[]
}

export interface Degradation {
  item: string
  reason: string
  suggestion?: string | null
}

export interface HostSnapshot {
  available?: boolean
  path?: string | null
  probed_at?: string | null
  stale?: boolean
  platform?: string | null
}

export interface ModelRecItem {
  key: string
  display: string
  params: string
  quant: string
  vram_required_gb: number
  ram_required_gb?: number | null
  context?: string | null
  fit?: string | null
  note?: string | null
  local?: { kind: string; base_url?: string; model: string; provider?: string } | null
}

export interface CloudPreset {
  key: string
  label: string
  base_url: string
  model: string
  scale?: string | null
}

export interface Recommendation {
  generated_at?: string | null
  hardware_summary?: {
    has_gpu?: boolean
    gpu_count?: number
    vram_total_gb?: number | null
    vram_accurate?: boolean | null
    ram_total_gb?: number | null
    cpu_cores?: number | null
  } | null
  tier?: { key: string; label: string; uncertain?: boolean } | null
  tier_range_gb?: { min?: number | null; max?: number | null } | null
  rationale?: string
  primary?: ModelRecItem | null
  items?: ModelRecItem[]
  cloud?: { recommended?: boolean; reason?: string | null; presets?: CloudPreset[] } | null
  degradations?: Degradation[]
  local_defaults?: { base_url?: string; model?: string; provider?: string } | null
}

export interface HardwarePayload {
  environment?: Record<string, unknown>
  cpu?: HardwareCpu
  memory?: HardwareMemory
  disks?: HardwareDisk[]
  gpus?: HardwareGpu[]
  gpu_vram?: HardwareVram
  network?: HardwareNetwork
  degradations?: Degradation[]
  sources?: string[]
  host_snapshot?: HostSnapshot
  probed_at?: string | null
  probe_ms?: number | null
  recommendation?: Recommendation
}

/** ============================== 端点与运行配置 ============================== */

export interface EndpointItem {
  id: number
  tenant_id: number
  name: string
  kind: string
  kind_label?: string
  provider?: string | null
  base_url: string
  model: string
  param_scale?: string | null
  has_api_key?: boolean
  api_key_hint?: string | null
  enabled: boolean
  is_active: boolean
  is_effective?: boolean
  source?: string | null
  remark?: string | null
  last_test_at?: string | null
  last_test_ok?: boolean | null
  last_test_latency_ms?: number | null
  last_test_message?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface RuntimeSnapshot {
  ai_enabled: boolean
  ai_mode: string
  base_url: string
  model: string
  api_key_configured: boolean
  api_key_hint?: string | null
  ai_ready: boolean
}

export interface OverviewStats {
  total: number
  enabled: number
  local: number
  cloud: number
  tested: number
  test_ok: number
}

export interface OverviewOut {
  active_endpoint?: EndpointItem | null
  active_endpoint_id?: number | null
  runtime: RuntimeSnapshot
  stats: OverviewStats
  endpoints: EndpointItem[]
  kinds: { key: string; label: string }[]
  cloud_presets: CloudPreset[]
  local_defaults?: { base_url?: string; model?: string; provider?: string } | null
  env_path?: string | null
}

export interface EndpointListOut {
  items: EndpointItem[]
  total: number
  active_endpoint_id?: number | null
  runtime: RuntimeSnapshot
}

export interface TestStep {
  step: string
  ok: boolean
  detail?: string | null
}

export interface TestResult {
  ok: boolean
  kind?: string
  checked_url?: string | null
  suggested_base_url?: string | null
  model?: string | null
  latency_ms?: number | null
  models?: string[]
  version?: string | null
  model_available?: boolean | null
  message?: string | null
  steps?: TestStep[]
  endpoint_id?: number | null
  endpoint_name?: string | null
  tested_at?: string | null
  runtime?: RuntimeSnapshot | null
}

export interface ApplyResult {
  endpoint?: EndpointItem | null
  test?: TestResult | null
  runtime?: RuntimeSnapshot | null
}

export interface EndpointPayload {
  name: string
  kind: string
  base_url: string
  model: string
  api_key?: string | null
  param_scale?: string | null
  provider?: string | null
  enabled?: boolean
  is_active?: boolean
  source?: string | null
  remark?: string | null
}

/** ============================== 接口定义 ============================== */

/** 本机硬件探测（CPU / 内存 / GPU 显存 / 磁盘 / 网络出口） */
export function fetchHardware(refresh = true) {
  return request.get<any, ApiResponse<HardwarePayload>>('/model/hardware', { params: { refresh } })
}

/** 按显存分档的模型推荐 */
export function fetchRecommend(includeHardware = false) {
  return request.get<any, ApiResponse<{ recommendation: Recommendation; probe?: HardwarePayload }>>(
    '/model/recommend',
    { params: { include_hardware: includeHardware } },
  )
}

/** 模型中心概览 */
export function fetchOverview() {
  return request.get<any, ApiResponse<OverviewOut>>('/model/overview')
}

/** 接入端点列表 */
export function fetchEndpoints() {
  return request.get<any, ApiResponse<EndpointListOut>>('/model/endpoints')
}

/** 新增接入端点 */
export function createEndpoint(payload: EndpointPayload) {
  return request.post<any, ApiResponse<EndpointItem>>('/model/endpoints', payload)
}

/** 修改接入端点 */
export function updateEndpoint(id: number, payload: Partial<EndpointPayload>) {
  return request.put<any, ApiResponse<EndpointItem>>(`/model/endpoints/${id}`, payload)
}

/** 删除接入端点 */
export function deleteEndpoint(id: number) {
  return request.delete<any, ApiResponse<{ id: number; deleted: boolean }>>(`/model/endpoints/${id}`)
}

/** 连通性自检（支持未保存配置） */
export function testEndpoint(payload: {
  id?: number | null
  kind: string
  base_url?: string | null
  model?: string | null
  api_key?: string | null
}) {
  return request.post<any, ApiResponse<TestResult>>('/model/test', payload)
}

/** 对已保存端点做连通性自检 */
export function testSavedEndpoint(id: number) {
  return request.post<any, ApiResponse<TestResult>>(`/model/endpoints/${id}/test`)
}

/** 设为当前生效端点 */
export function activateEndpoint(id: number) {
  return request.post<any, ApiResponse<{ id: number; is_active: boolean }>>(
    `/model/endpoints/${id}/activate`,
  )
}

/** 生效端点回写运行配置（.env） */
export function syncEndpointEnv(id: number, applyToEnv = true) {
  return request.post<any, ApiResponse<Record<string, unknown>>>(
    `/model/endpoints/${id}/sync-env`,
    { id, apply_to_env: applyToEnv },
  )
}

/** 一键接入（落库 + 自检 + 生效） */
export function applyEndpoint(payload: {
  mode: 'local' | 'cloud'
  name?: string | null
  base_url?: string | null
  model?: string | null
  param_scale?: string | null
  api_key?: string | null
  verify?: boolean
  activate?: boolean
}) {
  return request.post<any, ApiResponse<ApplyResult>>('/model/apply', payload)
}
