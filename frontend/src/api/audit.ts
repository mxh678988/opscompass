import request from './request'
import type { ApiResponse } from './metrics'

/** ---------------------------------------------------------------- 类型 */

/** 安全日志级别定义 */
export interface SecurityLevel {
  value: string
  label: string
  description: string
  order: number
}

/** 安全事件类型与默认级别 */
export interface SecurityEvent {
  value: string
  label: string
  default_level: string
}

/** 安全日志文件元信息 */
export interface SecurityLogFile {
  path: string
  exists: boolean
  size_bytes: number
  max_bytes: number
  backup_count: number
}

/** 安全日志分级配置 */
export interface SecurityLogConfig {
  enabled: boolean
  min_level: string
  alert_level: string
  mirror_to_main: boolean
  file?: SecurityLogFile
}

/** 单条安全日志 */
export interface SecurityLogItem {
  time: string
  level: string
  event: string
  event_label: string
  username?: string | null
  ip?: string | null
  method?: string | null
  path?: string | null
  status?: string | null
  status_code?: string | null
  detail?: string | null
}

/** 安全日志统计 */
export interface SecurityLogStats {
  days: number
  total: number
  by_level: Record<string, number>
  by_event: Record<string, number>
  latest_critical: SecurityLogItem[]
  file: SecurityLogFile
  config: {
    enabled: boolean
    min_level: string
    alert_level: string
    mirror_to_main: boolean
  }
}

/** 分级字典（级别 + 事件 + 配置） */
export interface SecurityLogCatalog {
  levels: SecurityLevel[]
  events: SecurityEvent[]
  config: SecurityLogConfig
}

/** 分级查询结果 */
export interface SecurityLogEntries {
  level?: string | null
  event_type?: string | null
  days: number
  items: SecurityLogItem[]
  stats: SecurityLogStats
}

/** ---------------------------------------------------------------- 审计日志 */

/** 单条审计日志 */
export interface AuditLogItem {
  id: number
  tenant_id?: number | null
  user_id?: number | null
  username?: string | null
  event_type: string
  action?: string | null
  status: string
  status_code?: number | null
  method?: string | null
  path?: string | null
  client_ip?: string | null
  user_agent?: string | null
  detail?: string | null
  created_at?: string | null
}

/** 审计日志分页结果 */
export interface AuditLogPage {
  total: number
  page: number
  page_size: number
  items: AuditLogItem[]
}

/** 审计统计 */
export interface AuditStats {
  total: number
  by_event_type: Record<string, number>
  by_status: Record<string, number>
}

/** 审计日志查询 */
export function fetchAuditLogs(params: {
  event_type?: string
  status?: string
  username?: string
  keyword?: string
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}) {
  return request.get<any, ApiResponse<AuditLogPage>>('/audit/logs', { params })
}

/** 审计统计：近 N 天概览 */
export function fetchAuditStats(days = 7) {
  return request.get<any, ApiResponse<AuditStats>>('/audit/stats', { params: { days } })
}

/** 审计事件类型枚举 */
export function fetchAuditEventTypes() {
  return request.get<any, ApiResponse<string[]>>('/audit/event-types')
}

/** 清理过期审计日志（敏感操作，需 audit:export 权限） */
export function purgeAuditLogs() {
  return request.post<any, ApiResponse<Record<string, unknown>>>('/audit/purge')
}

/** ---------------------------------------------------------------- 接口 */

/** 分级字典：级别定义、事件默认级别、通道配置 */
export function fetchSecurityLogLevels() {
  return request.get<any, ApiResponse<SecurityLogCatalog>>('/audit/security-log/levels')
}

/** 分级查询：按级别/事件/天数筛选条目并返回统计 */
export function fetchSecurityLogEntries(params: {
  level?: string
  event_type?: string
  days?: number
  limit?: number
}) {
  return request.get<any, ApiResponse<SecurityLogEntries>>('/audit/security-log/entries', { params })
}
