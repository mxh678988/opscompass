import request from './request'
import type { ApiResponse, PageResult } from './metrics'

/** M10 人群包引擎：按预测概率区间/档位圈选用户 */
export interface AudienceSegmentIn {
  name: string
  target?: 'churn' | 'conversion'
  source_job_id?: number | null
  min_prob?: number | null
  max_prob?: number | null
  band?: 'high' | 'medium' | 'low' | null
  description?: string | null
}

export interface AudienceReuseIn {
  name: string
  target?: 'churn' | 'conversion'
  source_segment_id: number
  min_prob?: number | null
  max_prob?: number | null
  band?: 'high' | 'medium' | 'low' | null
  description?: string | null
}

export interface AudienceMember {
  id: number
  segment_id: number
  subject_key: string
  subject_name?: string | null
  probability: number
  band: string
  source_result_id?: number | null
  created_at?: string | null
}

export interface AudienceSegment {
  id: number
  tenant_id: number
  name: string
  target: string
  status: string
  source_job_id?: number | null
  min_prob?: number | null
  max_prob?: number | null
  band?: string | null
  member_count: number
  criteria?: unknown
  description?: string | null
  created_by?: string
  created_at?: string | null
  updated_at?: string | null
  members?: AudienceMember[]
}

export function createAudienceSegment(payload: AudienceSegmentIn) {
  return request.post<any, ApiResponse<AudienceSegment>>('/audience/segments', payload)
}

export function reuseAudienceSegment(payload: AudienceReuseIn) {
  return request.post<any, ApiResponse<AudienceSegment>>('/audience/segments/reuse', payload)
}

export function fetchAudienceSegments(params?: {
  keyword?: string
  target?: string
  status?: string
  page?: number
  size?: number
}) {
  return request.get<any, ApiResponse<PageResult<AudienceSegment>>>('/audience/segments', { params })
}

export function fetchAudienceSegment(segmentId: number) {
  return request.get<any, ApiResponse<AudienceSegment>>(`/audience/segments/${segmentId}`)
}

export function patchAudienceSegment(segmentId: number, payload: { status?: string; description?: string }) {
  return request.patch<any, ApiResponse<AudienceSegment>>(`/audience/segments/${segmentId}`, payload)
}
