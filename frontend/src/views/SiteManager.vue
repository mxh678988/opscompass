<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import {
  deleteSiteResource, fetchResourceSummary, fetchSiteResources, fetchSites,
  patchSiteResource, scanSiteResources,
  type ResourceSummaryOut, type SiteProject, type SiteResource,
} from '@/api/sites'

const sites = ref<SiteProject[]>([])
const siteId = ref<number | null>(null)
const resources = ref<SiteResource[]>([])
const summary = ref<ResourceSummaryOut | null>(null)
const loading = ref(false)
const scanning = ref(false)
const msg = reactive({ type: '', text: '' })
let timer: number | undefined
function tip(type: 'ok' | 'error', text: string) {
  msg.type = type
  msg.text = text
  if (timer) window.clearTimeout(timer)
  timer = window.setTimeout(() => (msg.text = ''), 5000)
}
function errText(e: any) { return e?.response?.data?.message || e?.message || '请求失败' }
function fmtSize(n?: number) {
  if (n === null || n === undefined) return '-'
  if (n >= 1048576) return `${(n / 1048576).toFixed(1)} MB`
  if (n >= 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${n} B`
}

const STATUS_LABEL: Record<string, string> = {
  ok: '正常', missing: '缺失', error: '异常', ignored: '忽略', new: '新增', updated: '已更新',
}
function stLabel(v?: string) { return v ? (STATUS_LABEL[v] ?? v) : '-' }

async function loadSites() {
  try {
    const res = await fetchSites()
    sites.value = res.data ?? []
    if (!siteId.value && sites.value.length) siteId.value = sites.value[0].id
  } catch (e) { tip('error', `站点加载失败：${errText(e)}`) }
}

async function loadResources() {
  if (!siteId.value) { resources.value = []; summary.value = null; return }
  loading.value = true
  try {
    const [r, s] = await Promise.all([
      fetchSiteResources(siteId.value),
      fetchResourceSummary(siteId.value),
    ])
    resources.value = r.data ?? []
    summary.value = s.data ?? null
  } catch (e) { tip('error', `资源加载失败：${errText(e)}`) }
  finally { loading.value = false }
}

async function doScan() {
  if (!siteId.value) return
  scanning.value = true
  try {
    const res = await scanSiteResources(siteId.value)
    tip('ok', `扫描完成：新增 ${res.data?.created ?? 0}，更新 ${res.data?.updated ?? 0}，标记缺失 ${res.data?.marked_missing ?? 0}`)
    await loadResources()
  } catch (e) { tip('error', `扫描失败：${errText(e)}`) }
  finally { scanning.value = false }
}

async function setResourceStatus(r: SiteResource, status: string) {
  try {
    await patchSiteResource(r.id, { status })
    tip('ok', `资源「${r.name}」已标记为${stLabel(status)}`)
    await loadResources()
  } catch (e) { tip('error', `更新失败：${errText(e)}`) }
}

async function doDelete(r: SiteResource) {
  if (!window.confirm(`确认删除资源「${r.name}」？`)) return
  try {
    await deleteSiteResource(r.id)
    tip('ok', '资源已删除')
    await loadResources()
  } catch (e) { tip('error', `删除失败：${errText(e)}`) }
}

watch(siteId, () => loadResources())
onMounted(async () => {
  await loadSites()
  await loadResources()
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>网站资源管理器</h1>
        <p class="page-sub">扫描、核对站点资源文件，保障发布内容完整</p>
      </div>
      <div class="head-actions">
        <select v-model="siteId" class="input select-inline">
          <option :value="null">请选择站点</option>
          <option v-for="s in sites" :key="s.id" :value="s.id">{{ s.name }}（{{ s.slug }}）</option>
        </select>
        <button class="btn primary" :disabled="!siteId || scanning" @click="doScan">{{ scanning ? '扫描中…' : '扫描资源' }}</button>
      </div>
    </div>

    <div v-if="msg.text" class="msg" :class="msg.type">{{ msg.text }}</div>

    <div v-if="summary" class="stat-row">
      <div class="stat-card">
        <span class="stat-num">{{ summary.total }}</span>
        <span class="stat-label">资源总数</span>
      </div>
      <div class="stat-card">
        <span class="stat-num">{{ fmtSize(summary.total_size_bytes) }}</span>
        <span class="stat-label">总体积</span>
      </div>
      <div class="stat-card" v-for="(cnt, type) in summary.by_type" :key="type">
        <span class="stat-num">{{ cnt }}</span>
        <span class="stat-label">{{ type }}</span>
      </div>
      <div class="stat-card" v-for="(cnt, st) in summary.by_status" :key="st">
        <span class="stat-num">{{ cnt }}</span>
        <span class="stat-label">{{ stLabel(st) }}</span>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><h3>资源清单</h3><button class="btn ghost sm" @click="loadResources">刷新</button></div>
      <div v-if="loading" class="loading">加载中…</div>
      <div v-else-if="!siteId" class="empty">
        <p class="empty-title">请先选择站点</p>
        <p class="empty-sub">在右上角选择一个站点查看其资源文件</p>
      </div>
      <div v-else-if="!resources.length" class="empty">
        <p class="empty-title">暂无资源记录</p>
        <p class="empty-sub">点击「扫描资源」从发布目录同步文件</p>
      </div>
      <table v-else class="table">
        <thead><tr><th>名称</th><th>类型</th><th>路径</th><th>大小</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="r in resources" :key="r.id">
            <td class="td-main">{{ r.name }}</td>
            <td><span class="tag">{{ r.resource_type }}</span></td>
            <td class="td-muted">{{ r.path }}</td>
            <td class="td-muted">{{ fmtSize(r.size_bytes) }}</td>
            <td><span class="badge" :class="r.status === 'ok' ? 'ok' : (r.status === 'missing' || r.status === 'error' ? 'error' : 'muted')">{{ stLabel(r.status) }}</span></td>
            <td class="ops">
              <button v-if="r.status !== 'ok'" class="btn ghost sm" @click="setResourceStatus(r, 'ok')">标正常</button>
              <button v-if="r.status !== 'missing'" class="btn ghost sm warn-text" @click="setResourceStatus(r, 'missing')">标缺失</button>
              <button class="btn ghost sm danger-text" @click="doDelete(r)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6); max-width: 1400px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-5); }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; }
.page-head h1 { margin: 0; font-size: 22px; }
.page-sub { margin: var(--space-1) 0 0; color: var(--color-text-muted); font-size: 13px; }
.head-actions { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; }
.select-inline { width: 220px; }
.card { background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-5); box-shadow: var(--shadow-sm); min-width: 0; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); flex-wrap: wrap; }
.card-head h3 { margin: 0; font-size: 16px; }
.btn { display: inline-flex; align-items: center; gap: var(--space-1); padding: var(--space-2) var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg); color: var(--color-text); font-size: 13px; cursor: pointer; transition: all var(--transition-fast); white-space: nowrap; }
.btn:hover { background: var(--color-bg-hover); }
.btn.primary { background: var(--color-primary); border-color: var(--color-primary); color: #fff; }
.btn.primary:hover { background: var(--color-primary-hover); }
.btn.primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn.ghost { background: transparent; }
.btn.sm { padding: 3px 10px; font-size: 12px; border-radius: var(--radius-sm); }
.warn-text { color: var(--color-warning); }
.danger-text { color: var(--color-error); }
.msg { padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); font-size: 13px; }
.msg.ok { background: var(--color-success-light); color: var(--color-success); border: 1px solid var(--color-success-border); }
.msg.error { background: var(--color-error-light); color: var(--color-error); border: 1px solid var(--color-error-border); }
.stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: var(--space-3); }
.stat-card { display: flex; flex-direction: column; gap: 2px; padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg); box-shadow: var(--shadow-sm); }
.stat-num { font-size: 24px; font-weight: 700; line-height: 1.1; }
.stat-label { font-size: 12px; color: var(--color-text-secondary); }
.table { width: 100%; }
.td-main { font-weight: 500; }
.td-muted { color: var(--color-text-muted); font-size: 12px; }
.ops { display: flex; gap: var(--space-1); white-space: nowrap; }
.badge { display: inline-block; padding: 1px 10px; border-radius: var(--radius-full); font-size: 12px; font-weight: 600; line-height: 1.7; background: var(--color-bg-subtle); color: var(--color-text-secondary); }
.badge.ok { background: var(--color-success-light); color: var(--color-success); }
.badge.error { background: var(--color-error-light); color: var(--color-error); }
.badge.muted { background: var(--color-bg-subtle); color: var(--color-text-muted); }
.tag { display: inline-block; padding: 0 8px; border-radius: var(--radius-sm); font-size: 12px; background: var(--color-primary-light); color: var(--color-primary); }
.loading { padding: var(--space-10); text-align: center; color: var(--color-text-muted); }
.empty { padding: var(--space-10) var(--space-4); text-align: center; border: 1px dashed var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-subtle); }
.empty-title { margin: 0 0 var(--space-1); font-weight: 600; color: var(--color-text-secondary); }
.empty-sub { margin: 0; font-size: 12px; color: var(--color-text-muted); }
</style>
