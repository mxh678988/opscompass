import request from './request'
import type { ApiResponse, TrendPoint } from './metrics'

/** ---------------------------------------------------------------- 类型 */

export interface BreakdownItem {
  dim_value: string
  value: number
  prev_value?: number | null
  delta_ratio?: number | null
  share?: number | null
}

export interface CompassMetric {
  code: string
  name: string
  unit: string
  precision: number
  has_data: boolean
  value: number
  prev_value?: number | null
  delta_ratio?: number | null
  stat_time?: string | null
  breakdown: BreakdownItem[]
  trend: TrendPoint[]
}

export interface CompassOut {
  granularity: string
  dim_key?: string | null
  dim_name?: string | null
  available_dim_keys: string[]
  dim_values: string[]
  latest_stat?: string | null
  items: CompassMetric[]
}

/** ---------------------------------------------------------------- 接口 */

/** 全景罗盘：整体口径 + 维度拆解 + 趋势 */
export function fetchCompass(params?: { granularity?: string; dim_key?: string; codes?: string }) {
  return request.get<any, ApiResponse<CompassOut>>('/metrics/compass', { params })
}

/** 已接入数据中出现过的维度键 */
export function fetchDimKeys() {
  return request.get<any, ApiResponse<string[]>>('/metrics/dim-keys')
}
