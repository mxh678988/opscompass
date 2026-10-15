<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createSite, deleteSite, fetchSites, previewSite, publishSite,
  type SiteProject, type SiteProjectIn,
} from '@/api/sites'

const sites = ref<SiteProject[]>([])
const loading = ref(false)
const msg = reactive({ type: '', text: '' })
let timer: number | undefined
function tip(type: 'ok' | 'warn' | 'error', text: string) {
  msg.type = type
  msg.text = text
  if (timer) window.clearTimeout(timer)
  timer = window.setTimeout(() => (msg.text = ''), 5000)
}
function errText(e: any) { return e?.response?.data?.message || e?.message || '请求失败' }
function dt(v?: string) { return v ? String(v).replace('T', ' ').slice(0, 19) : '-' }

const form = reactive<SiteProjectIn>({
  name: '', slug: '', description: '', template: 'basic',
  seo_title: '', seo_description: '', seo_keywords: '',
  geo_enabled: false, geo_region: '', geo_org_type: '',
  host_mode: 'link',
})
const submitting = ref(false)
const pendingId = ref<number | null>(null)
const previewUrl = ref('')

async function load() {
  loading.value = true
  try {
    const res = await fetchSites()
    sites.value = res.data ?? []
  } catch (e) { tip('error', `站点加载失败：${errText(e)}`) }
  finally { loading.value = false }
}

async function submit() {
  if (!form.name.trim() || !form.slug.trim()) { tip('warn', '请填写站点名称与 slug'); return }
  if (!/^[a-z0-9-]+$/.test(form.slug)) { tip('warn', 'slug 仅支持小写字母、数字与中划线'); return }
  submitting.value = true
  try {
    await createSite({ ...form })
    tip('ok', '站点创建成功')
    Object.assign(form, { name: '', slug: '', description: '', template: 'basic', seo_title: '', seo_description: '', seo_keywords: '', geo_enabled: false, geo_region: '', geo_org_type: '', host_mode: 'link' })
    await load()
  } catch (e) { tip('error', `创建失败：${errText(e)}`) }
  finally { submitting.value = false }
}

async function doPublish(site: SiteProject) {
  if (pendingId.value !== null) return
  pendingId.value = site.id
  try {
    await publishSite(site.id)
    tip('ok', `「${site.name}」已发布`)
    await load()
  } catch (e) { tip('error', `发布失败：${errText(e)}`) }
  finally { pendingId.value = null }
}

async function doPreview(site: SiteProject) {
  if (pendingId.value !== null) return
  pendingId.value = site.id
  try {
    const html = await previewSite(site.id)
    previewUrl.value = html ?? ''
  } catch (e) { tip('error', `预览失败：${errText(e)}`) }
  finally { pendingId.value = null }
}

async function doDelete(site: SiteProject) {
  if (pendingId.value !== null) return
  if (!window.confirm(`确认删除站点「${site.name}」及其资源？删除后不可恢复。`)) return
  pendingId.value = site.id
  try {
    await deleteSite(site.id)
    tip('ok', '站点已删除')
    await load()
  } catch (e) { tip('error', `删除失败：${errText(e)}`) }
  finally { pendingId.value = null }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>响应式网站</h1>
        <p class="page-sub">创建响应式营销站点，配置 SEO / GEO 元信息并发布</p>
      </div>
    </div>

    <div v-if="msg.text" class="msg" :class="msg.type">{{ msg.text }}</div>

    <div class="module-grid two-col">
      <div class="card">
        <div class="card-head"><h3>创建站点</h3><span class="hint">填写基础信息与 SEO 配置</span></div>
        <form class="form" @submit.prevent="submit">
          <div class="row">
            <div class="field grow">
              <label>站点名称 <em>*</em></label>
              <input v-model="form.name" class="input" placeholder="例如：新品发布页" required />
            </div>
            <div class="field grow">
              <label>Slug <em>*</em></label>
              <input v-model="form.slug" class="input" placeholder="例如：launch-2026" required />
            </div>
          </div>
          <div class="field">
            <label>站点描述</label>
            <textarea v-model="form.description" class="input area" rows="2"></textarea>
          </div>
          <div class="row">
            <div class="field grow">
              <label>模板</label>
              <select v-model="form.template" class="input">
                <option value="basic">基础页</option>
                <option value="marketing">营销页</option>
                <option value="landing">落地页</option>
              </select>
            </div>
            <div class="field grow">
              <label>托管方式</label>
              <select v-model="form.host_mode" class="input">
                <option value="link">链接托管</option>
                <option value="space">空间托管</option>
              </select>
            </div>
          </div>
          <div class="field">
            <label>SEO 标题</label>
            <input v-model="form.seo_title" class="input" placeholder="浏览器标题与搜索引擎展示标题" />
          </div>
          <div class="field">
            <label>SEO 描述</label>
            <textarea v-model="form.seo_description" class="input area" rows="2"></textarea>
          </div>
          <div class="field">
            <label>SEO 关键词</label>
            <input v-model="form.seo_keywords" class="input" placeholder="逗号分隔" />
          </div>
          <label class="check"><input v-model="form.geo_enabled" type="checkbox" /> 启用 GEO（地域增强）</label>
          <div v-if="form.geo_enabled" class="row">
            <div class="field grow">
              <label>地域</label>
              <input v-model="form.geo_region" class="input" placeholder="例如：中国·深圳" />
            </div>
            <div class="field grow">
              <label>组织类型</label>
              <input v-model="form.geo_org_type" class="input" placeholder="例如：LocalBusiness" />
            </div>
          </div>
          <button class="btn primary block" type="submit" :disabled="submitting">{{ submitting ? '创建中…' : '创建站点' }}</button>
        </form>
      </div>

      <div class="card">
        <div class="card-head"><h3>站点列表</h3><button class="btn ghost sm" @click="load">刷新</button></div>
        <div v-if="loading" class="loading">加载中…</div>
        <div v-else-if="!sites.length" class="empty">
          <p class="empty-title">暂无站点</p>
          <p class="empty-sub">在左侧创建第一个响应式站点</p>
        </div>
        <table v-else class="table">
          <thead><tr><th>名称</th><th>Slug</th><th>状态</th><th>SEO</th><th>更新时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="s in sites" :key="s.id">
              <td class="td-main">{{ s.name }}</td>
              <td class="td-muted">{{ s.slug }}</td>
              <td><span class="badge" :class="s.status === 'published' ? 'ok' : 'muted'">{{ s.status === 'published' ? '已发布' : (s.status || '草稿') }}</span></td>
              <td class="td-muted">{{ s.seo_title ? '已配置' : '-' }}</td>
              <td class="td-muted">{{ dt(s.updated_at || s.created_at) }}</td>
              <td class="ops">
                <button class="btn ghost sm" :disabled="pendingId === s.id" @click="doPreview(s)">预览</button>
                <button v-if="s.status !== 'published'" class="btn ghost sm" :disabled="pendingId === s.id" @click="doPublish(s)">{{ pendingId === s.id ? '处理中…' : '发布' }}</button>
                <button class="btn ghost sm danger-text" :disabled="pendingId === s.id" @click="doDelete(s)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="previewUrl" class="mask" @click.self="previewUrl = ''">
      <div class="preview-panel">
        <div class="preview-head">
          <h3>站点预览</h3>
          <button class="btn ghost sm" @click="previewUrl = ''">关闭</button>
        </div>
        <iframe class="preview-frame" :srcdoc="previewUrl" sandbox="allow-scripts"></iframe>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6); max-width: 1400px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-5); }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; }
.page-head h1 { margin: 0; font-size: 22px; }
.page-sub { margin: var(--space-1) 0 0; color: var(--color-text-muted); font-size: 13px; }
.module-grid { display: grid; gap: var(--space-5); }
.module-grid.two-col { grid-template-columns: 400px 1fr; }
@media (max-width: 1024px) { .module-grid.two-col { grid-template-columns: 1fr; } }
.card { background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-5); box-shadow: var(--shadow-sm); min-width: 0; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); flex-wrap: wrap; }
.card-head h3 { margin: 0; font-size: 16px; }
.hint { font-size: 12px; color: var(--color-text-muted); }
.form { display: flex; flex-direction: column; gap: var(--space-4); }
.field { display: flex; flex-direction: column; gap: var(--space-1); }
.field label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.field label em { color: var(--color-error); font-style: normal; }
.input { width: 100%; }
.input.area { resize: vertical; }
.row { display: flex; gap: var(--space-3); }
.row .grow { flex: 1; min-width: 0; }
.check { display: flex; align-items: center; gap: var(--space-2); font-size: 13px; color: var(--color-text-secondary); cursor: pointer; }
.btn { display: inline-flex; align-items: center; gap: var(--space-1); padding: var(--space-2) var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg); color: var(--color-text); font-size: 13px; cursor: pointer; transition: all var(--transition-fast); white-space: nowrap; }
.btn:hover { background: var(--color-bg-hover); }
.btn.primary { background: var(--color-primary); border-color: var(--color-primary); color: var(--color-text-on-primary); }
.btn.primary:hover { background: var(--color-primary-hover); }
.btn.primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn.ghost { background: transparent; }
.btn.sm { padding: 3px 10px; font-size: 12px; border-radius: var(--radius-sm); }
.btn.block { width: 100%; justify-content: center; padding: var(--space-3); }
.danger-text { color: var(--color-error); }
.msg { padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); font-size: 13px; }
.msg.ok { background: var(--color-success-light); color: var(--color-success); border: 1px solid var(--color-success-border); }
.msg.error { background: var(--color-error-light); color: var(--color-error); border: 1px solid var(--color-error-border); }
.msg.warn { background: var(--color-warning-light); color: var(--color-warning); border: 1px solid var(--color-warning-border); }
.table { width: 100%; }
.td-main { font-weight: 500; }
.td-muted { color: var(--color-text-muted); font-size: 12px; }
.ops { display: flex; gap: var(--space-1); white-space: nowrap; }
.badge { display: inline-block; padding: 1px 10px; border-radius: var(--radius-full); font-size: 12px; font-weight: 600; line-height: 1.7; background: var(--color-bg-subtle); color: var(--color-text-secondary); }
.badge.ok { background: var(--color-success-light); color: var(--color-success); }
.badge.muted { background: var(--color-bg-subtle); color: var(--color-text-muted); }
.loading { padding: var(--space-10); text-align: center; color: var(--color-text-muted); }
.empty { padding: var(--space-10) var(--space-4); text-align: center; border: 1px dashed var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-subtle); }
.empty-title { margin: 0 0 var(--space-1); font-weight: 600; color: var(--color-text-secondary); }
.empty-sub { margin: 0; font-size: 12px; color: var(--color-text-muted); }
.mask { position: fixed; inset: 0; background: var(--mask-overlay); display: flex; justify-content: center; align-items: center; z-index: 100; }
.preview-panel { width: min(1100px, 94vw); height: 90vh; background: var(--color-bg); border-radius: var(--radius-lg); display: flex; flex-direction: column; overflow: hidden; box-shadow: var(--shadow-card); }
.preview-head { display: flex; align-items: center; justify-content: space-between; padding: var(--space-3) var(--space-5); border-bottom: 1px solid var(--color-border-light); }
.preview-head h3 { margin: 0; font-size: 16px; }
.preview-frame { flex: 1; width: 100%; border: none; }
</style>
