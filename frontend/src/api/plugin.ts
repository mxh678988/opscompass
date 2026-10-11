import request from './request'
import type { ApiResponse, PageResult } from './metrics'

/** ============================== 类型定义 ============================== */

export type PluginKind = 'official' | 'community'
export type PluginState = 'discovered' | 'installed' | 'enabled' | 'disabled' | 'uninstalled'

export interface PluginPermission {
  code?: string
  name?: string
}
export type PermItem = string | PluginPermission
export type Permissions = PermItem[]

export interface PluginItem {
  plugin_id: string
  name: string
  version: string
  kind: PluginKind
  min_kernel_version?: string | null
  entry?: string | null
  namespace?: { tables?: string | null; events?: string | null; permissions?: string | null } | null
  permissions?: Permissions
  roles?: { code?: string; name?: string; permissions?: Permissions }[]
  state: PluginState
  /** 以下为详情接口补充字段 */
  registered?: boolean
  installed_version?: string | null
  installed_at?: string | null
  checksum?: string | null
  description?: string | null
  signature_status?: string | null
}

export interface PluginListOut extends PageResult<PluginItem> {}

export interface PluginActionOut {
  plugin_id: string
  state: PluginState
  registered_id?: number | null
  tables?: string[]
}

/** ============================== 接口定义 ============================== */

/** 插件市场列表（kind / state / keyword 可选过滤） */
export function fetchPlugins(params: {
  kind?: PluginKind | ''
  state?: PluginState | ''
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get<any, ApiResponse<PluginListOut>>('/plugins/market', { params })
}

/** 插件详情 */
export function fetchPluginDetail(pluginId: string) {
  return request.get<any, ApiResponse<PluginItem>>(`/plugins/market/${pluginId}`)
}

/** 安装并启用插件 */
export function installPlugin(pluginId: string) {
  return request.post<any, ApiResponse<PluginActionOut>>(`/plugins/market/${pluginId}/install`)
}

/** 启用插件 */
export function enablePlugin(pluginId: string) {
  return request.post<any, ApiResponse<PluginActionOut>>(`/plugins/market/${pluginId}/enable`)
}

/** 禁用插件 */
export function disablePlugin(pluginId: string) {
  return request.post<any, ApiResponse<PluginActionOut>>(`/plugins/market/${pluginId}/disable`)
}

/** 卸载插件 */
export function uninstallPlugin(pluginId: string) {
  return request.post<any, ApiResponse<PluginActionOut>>(`/plugins/market/${pluginId}/uninstall`)
}
