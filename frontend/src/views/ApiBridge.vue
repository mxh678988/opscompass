<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createApiTask, deleteApiTemplate, fetchApiTasks, fetchApiTemplates,
  type ApiApplyTask, type ApiPlatformTemplate,
} from '@/api/apiBridge'

const templates = ref<ApiPlatformTemplate[]>([])
const tasks = ref<ApiApplyTask[]>([])
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
function pickList(data: any): any[] {
  if (!data) return []
  if (Array.isArray(data)) return data
  if (Array.isArray(data.items)) return data.items
  if (Array.isArray(data.results)) return data.results
  if (Array.isArray(data.data)) return data.data
  return []
}

const applyForm = reactive({ platform_id: null as number | null, platform: '', account: '', password: '', remark: '' })
const submitting = ref(false)
const STATUS_LABEL: Record<string, string> = {
  pending: '待申请', applying: '申请中', success: '成功', failed: '失败', manual: '需人工',
}
function stLabel(v?: string) { return v ? (STATUS_LABEL[v] ?? v) : '-' }
function stCls(v?: string) {
  if (v === 'success') return 'ok'
  if (v === 'failed') return 'error'
  if (v === 'applying' || v === 'manual') return 'warn'
  return 'muted'
}

async function load() {
  loading.value = true
  try {
    const [t, k] = await Promise.all([fetchApiTemplates({}), fetchApiTasks({})])
    templates.value = pickList(t.data)
    tasks.value = pickList(k.data)
  } catch (e) { tip('error', `数据加载失败：${errText(e)}`) }
  finally { loading.value = false }
}

async function submitApply() {
  if (!applyForm.platform_id && !applyForm.platform.trim()) { tip('warn', '请选择平台模板或填写平台名称'); return }
  if (!applyForm.account.trim()) { tip('warn', '请填写账号'); return }
  submitting.value = true
  try {
    await createApiTask({
      platform_id: applyForm.platform_id,
      platform: applyForm.platform || undefined,
      account: applyForm.account,
      password: applyForm.password || undefined,
      remark: applyForm.remark || null,
    })
    tip('ok', 'API 申请任务已创建（凭据服务端加密保存）')
    Object.assign(applyForm, { platform_id: null, platform: '', account: '', password: '', remark: '' })
    await load()
  } catch (e) { tip('error', `申请失败：${errText(e)}`) }
  finally { submitting.value = false }
}

async function removeTemplate(tpl: ApiPlatformTemplate) {
  if (!window.confirm(`确认删除平台模板「${tpl.name}」？`)) return
  try {
    await deleteApiTemplate(tpl.id)
    tip('ok', '模板已删除')
    await load()
  } catch (e) { tip('error', `删除失败：${errText(e)}`) }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>API 代申请助手</h1>
        <p class="page-sub">平台模板引导 + 申请任务跟踪，凭据由服务端加密保管</p>
      </div>
    </div>

    <div v-if="msg.text" class="msg" :class="msg.type">{{ msg.text }}</div>

    <div class="module-grid two-col">
      <div class="card">
        <div class="card-head"><h3>发起 API 申请</h3><span class="hint">选择平台模板后填写账号信息</span></div>
        <form class="form" @submit.prevent="submitApply">
          <div class="field">
            <label>平台模板</label>
            <select v-model="applyForm.platform_id" class="input">
              <option :value="null">直接填写平台名</option>
              <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </div>
          <div v-if="!applyForm.platform_id" class="field">
            <label>平台名称</label>
            <input v-model="applyForm.platform" class="input" placeholder="例如：微信支付" />
          </div>
          <div class="field">
            <label>账号 <em>*</em></label>
            <input v-model="applyForm.account" class="input" placeholder="申请账号 / 邮箱" required />
          </div>
          <div class="field">
            <label>密码 / 密钥</label>
            <input v-model="applyForm.password" class="input" type="password" placeholder="仅用于申请，加密存储" />
          </div>
          <div class="field">
            <label>备注</label>
            <textarea v-model="applyForm.remark" class="input area" rows="2"></textarea>
          </div>
          <button class="btn primary block" type="submit" :disabled="submitting">{{ submitting ? '提交中…' : '创建申请任务' }}</button>
        </form>
      </div>

      <div class="card">
        <div class="card-head"><h3>申请任务</h3><button class="btn ghost sm" @click="load">刷新</button></div>
        <div v-if="loading" class="loading">加载中…</div>
        <div v-else-if="!tasks.length" class="empty"><p class="empty-title">暂无申请任务</p><p class="empty-sub">发起申请后在此跟踪进度</p></div>
        <table v-else class="table">
          <thead><tr><th>平台</th><th>账号</th><th>状态</th><th>进度</th><th>结果</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="t in tasks" :key="t.id">
              <td class="td-main">{{ t.platform }}</td>
              <td class="td-muted">{{ t.account }}</td>
              <td><span class="badge" :class="stCls(t.status)">{{ stLabel(t.status) }}</span></td>
              <td class="td-muted">{{ t.progress ?? 0 }}%</td>
              <td class="td-muted">{{ t.result_message || t.error || '-' }}</td>
              <td class="td-muted">{{ dt(t.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><h3>平台模板</h3><span class="hint">常用平台的申请引导模板</span></div>
      <div v-if="loading" class="loading">加载中…</div>
      <div v-else-if="!templates.length" class="empty"><p class="empty-title">暂无模板</p><p class="empty-sub">模板由管理员配置</p></div>
      <table v-else class="table">
        <thead><tr><th>名称</th><th>分类</th><th>申请地址</th><th>人工流程</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="t in templates" :key="t.id">
            <td class="td-main">{{ t.name }}</td>
            <td><span class="tag">{{ t.category || '通用' }}</span></td>
            <td class="td-muted">{{ t.apply_url }}</td>
            <td>{{ t.requires_manual ? '是' : '否' }}</td>
            <td><span class="badge" :class="t.enabled === false ? 'muted' : 'ok'">{{ t.enabled === false ? '停用' : '启用' }}</span></td>
            <td class="ops"><button class="btn ghost sm danger-text" @click="removeTemplate(t)">删除</button></td>
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
.badge.error { background: var(--color-error-light); color: var(--color-error); }
.badge.warn { background: var(--color-warning-light); color: var(--color-warning); }
.badge.muted { background: var(--color-bg-subtle); color: var(--color-text-muted); }
.tag { display: inline-block; padding: 0 8px; border-radius: var(--radius-sm); font-size: 12px; background: var(--color-primary-light); color: var(--color-primary); }
.loading { padding: var(--space-10); text-align: center; color: var(--color-text-muted); }
.empty { padding: var(--space-10) var(--space-4); text-align: center; border: 1px dashed var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-subtle); }
.empty-title { margin: 0 0 var(--space-1); font-weight: 600; color: var(--color-text-secondary); }
.empty-sub { margin: 0; font-size: 12px; color: var(--color-text-muted); }
</style>
