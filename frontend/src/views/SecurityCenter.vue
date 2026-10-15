<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createExport, createImport, fetchExports, fetchImports,
  type ExportRecord, type ImportRecord,
} from '@/api/securityTransfer'

const imports = ref<ImportRecord[]>([])
const exports_ = ref<ExportRecord[]>([])
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
function dt(v?: string | null) { return v ? String(v).replace('T', ' ').slice(0, 19) : '-' }
const STATUS_LABEL: Record<string, string> = { pending: '待处理', processing: '处理中', done: '已完成', failed: '失败' }
function stLabel(v?: string) { return v ? (STATUS_LABEL[v] ?? v) : '-' }
function stCls(v?: string) { return v === 'done' ? 'ok' : (v === 'failed' ? 'error' : 'muted') }

const importForm = reactive({ source_path: '', target_dir: '', archive_type: 'zip' as 'zip' | 'tar.gz' })
const exportForm = reactive({ source_dir: '', target_name: '', encrypted: false, password: '' })
const submitting = ref(false)

async function load() {
  loading.value = true
  try {
    const [i, e] = await Promise.all([fetchImports(), fetchExports()])
    imports.value = i.data?.items ?? i.data?.imports ?? []
    exports_.value = e.data?.items ?? e.data?.exports ?? []
  } catch (err) { tip('error', `记录加载失败：${errText(err)}`) }
  finally { loading.value = false }
}

async function submitImport() {
  if (!importForm.source_path.trim() || !importForm.target_dir.trim()) { tip('warn', '请填写来源路径与目标目录'); return }
  submitting.value = true
  try {
    const res = await createImport({ ...importForm })
    tip('ok', `导入任务已创建（状态：${res.data?.status ?? '处理中'}）`)
    Object.assign(importForm, { source_path: '', target_dir: '', archive_type: 'zip' })
    await load()
  } catch (e) { tip('error', `导入失败：${errText(e)}`) }
  finally { submitting.value = false }
}

async function submitExport() {
  if (!exportForm.source_dir.trim() || !exportForm.target_name.trim()) { tip('warn', '请填写来源目录与目标文件名'); return }
  if (exportForm.encrypted && !exportForm.password) { tip('warn', '启用加密时请填写密码'); return }
  submitting.value = true
  try {
    const res = await createExport({
      source_dir: exportForm.source_dir,
      target_name: exportForm.target_name,
      encrypted: exportForm.encrypted,
      password: exportForm.encrypted ? exportForm.password : null,
    })
    if (res.data?.plugin_required) tip('warn', '加密导出需要付费插件，当前任务未加密执行')
    else tip('ok', `导出任务已创建（状态：${res.data?.status ?? '处理中'}）`)
    Object.assign(exportForm, { source_dir: '', target_name: '', encrypted: false, password: '' })
    await load()
  } catch (e) { tip('error', `导出失败：${errText(e)}`) }
  finally { submitting.value = false }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>压缩安全中心</h1>
        <p class="page-sub">安全导入解压与导出压缩，加密能力由付费插件提供</p>
      </div>
    </div>

    <div v-if="msg.text" class="msg" :class="msg.type">{{ msg.text }}</div>

    <div class="module-grid two-col">
      <div class="card">
        <div class="card-head"><h3>安全导入（解压）</h3><span class="hint">校验路径安全性后解压归档</span></div>
        <form class="form" @submit.prevent="submitImport">
          <div class="field">
            <label>来源归档路径 <em>*</em></label>
            <input v-model="importForm.source_path" class="input" placeholder="例如：/data/uploads/backup.zip" required />
          </div>
          <div class="field">
            <label>目标目录 <em>*</em></label>
            <input v-model="importForm.target_dir" class="input" placeholder="例如：/data/sites/demo" required />
          </div>
          <div class="field">
            <label>归档类型</label>
            <select v-model="importForm.archive_type" class="input">
              <option value="zip">ZIP</option>
              <option value="tar.gz">TAR.GZ</option>
            </select>
          </div>
          <button class="btn primary block" type="submit" :disabled="submitting">{{ submitting ? '提交中…' : '发起导入' }}</button>
        </form>
      </div>

      <div class="card">
        <div class="card-head"><h3>安全导出（压缩）</h3><span class="hint">将目录打包为归档文件</span></div>
        <form class="form" @submit.prevent="submitExport">
          <div class="field">
            <label>来源目录 <em>*</em></label>
            <input v-model="exportForm.source_dir" class="input" placeholder="例如：/data/sites/demo" required />
          </div>
          <div class="field">
            <label>目标文件名 <em>*</em></label>
            <input v-model="exportForm.target_name" class="input" placeholder="例如：demo-backup" required />
          </div>
          <label class="check"><input v-model="exportForm.encrypted" type="checkbox" /> 启用加密（需付费插件）</label>
          <div v-if="exportForm.encrypted" class="field">
            <label>加密密码</label>
            <input v-model="exportForm.password" class="input" type="password" placeholder="加密口令" />
          </div>
          <button class="btn primary block" type="submit" :disabled="submitting">{{ submitting ? '提交中…' : '发起导出' }}</button>
        </form>
      </div>
    </div>

    <div class="module-grid two-col">
      <div class="card">
        <div class="card-head"><h3>导入记录</h3><button class="btn ghost sm" @click="load">刷新</button></div>
        <div v-if="loading" class="loading">加载中…</div>
        <div v-else-if="!imports.length" class="empty"><p class="empty-title">暂无导入记录</p><p class="empty-sub">发起导入后在此查看进度</p></div>
        <table v-else class="table">
          <thead><tr><th>来源</th><th>类型</th><th>文件数</th><th>状态</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="r in imports" :key="r.id">
              <td class="td-main">{{ r.source_name }}</td>
              <td><span class="tag">{{ r.archive_type }}</span></td>
              <td>{{ r.file_count }}</td>
              <td><span class="badge" :class="stCls(r.status)">{{ stLabel(r.status) }}</span></td>
              <td class="td-muted">{{ dt(r.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="card-head"><h3>导出记录</h3><button class="btn ghost sm" @click="load">刷新</button></div>
        <div v-if="loading" class="loading">加载中…</div>
        <div v-else-if="!exports_.length" class="empty"><p class="empty-title">暂无导出记录</p><p class="empty-sub">发起导出后在此查看结果</p></div>
        <table v-else class="table">
          <thead><tr><th>文件名</th><th>加密</th><th>文件数</th><th>状态</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="r in exports_" :key="r.id">
              <td class="td-main">{{ r.target_name }}</td>
              <td>{{ r.encrypted ? '已加密' : '未加密' }}</td>
              <td>{{ r.file_count }}</td>
              <td><span class="badge" :class="stCls(r.status)">{{ stLabel(r.status) }}</span></td>
              <td class="td-muted">{{ dt(r.created_at) }}</td>
            </tr>
          </tbody>
        </table>
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
.module-grid.two-col { grid-template-columns: 1fr 1fr; }
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
.check { display: flex; align-items: center; gap: var(--space-2); font-size: 13px; color: var(--color-text-secondary); cursor: pointer; }
.btn { display: inline-flex; align-items: center; gap: var(--space-1); padding: var(--space-2) var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg); color: var(--color-text); font-size: 13px; cursor: pointer; transition: all var(--transition-fast); white-space: nowrap; }
.btn:hover { background: var(--color-bg-hover); }
.btn.primary { background: var(--color-primary); border-color: var(--color-primary); color: var(--color-text-on-primary); }
.btn.primary:hover { background: var(--color-primary-hover); }
.btn.primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn.ghost { background: transparent; }
.btn.sm { padding: 3px 10px; font-size: 12px; border-radius: var(--radius-sm); }
.btn.block { width: 100%; justify-content: center; padding: var(--space-3); }
.msg { padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); font-size: 13px; }
.msg.ok { background: var(--color-success-light); color: var(--color-success); border: 1px solid var(--color-success-border); }
.msg.error { background: var(--color-error-light); color: var(--color-error); border: 1px solid var(--color-error-border); }
.msg.warn { background: var(--color-warning-light); color: var(--color-warning); border: 1px solid var(--color-warning-border); }
.table { width: 100%; }
.td-main { font-weight: 500; }
.td-muted { color: var(--color-text-muted); font-size: 12px; }
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
