import request from './request'

export interface DataSourceItem {
  id: number
  tenant_id: number
  code: string
  name: string
  ds_type: string
  host?: string | null
  port?: number | null
  db_name?: string | null
  username?: string | null
  extra_config?: Record<string, unknown> | null
  status: string
  last_sync_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface PageResult<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

/** 数据源列表 */
export function fetchDataSources(params?: { keyword?: string; page?: number; page_size?: number }) {
  return request.get<any, ApiResponse<PageResult<DataSourceItem>>>('/datasources', { params })
}

/** 新建数据源 */
export function createDataSource(payload: Partial<DataSourceItem> & { code: string; name: string; ds_type: string; password?: string }) {
  return request.post<any, ApiResponse<DataSourceItem>>('/datasources', payload)
}

/** 更新数据源 */
export function updateDataSource(code: string, payload: Partial<DataSourceItem> & { password?: string }) {
  return request.put<any, ApiResponse<DataSourceItem>>(`/datasources/${code}`, payload)
}

/** 删除数据源 */
export function deleteDataSource(code: string) {
  return request.delete<any, ApiResponse<{ code: string; deleted: boolean }>>(`/datasources/${code}`)
}
