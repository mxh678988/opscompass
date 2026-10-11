<template>
  <div class="audit-page">
    <!-- 页面头 -->
    <div class="page-head">
      <div>
        <h2>审计日志</h2>
        <p class="sub">全域操作审计 · 追踪关键行为轨迹</p>
      </div>
      <div class="head-actions">
        <span class="badge">audit: view</span>
        <button class="btn ghost" @click="loadAll" :disabled="loading">
          {{ loading ? '加载中…' : '刷新' }}
        </button>
        <button class="btn danger" @click="confirmPurge" :disabled="loading || purging">
          {{ purging ? '清理中…' : '清理过期日志' }}
        </button>
      </div>
    </div>

    <!-- 消息提示 -->
    <div v-if="msg.text" :class="['msg', msg.type]">{{ msg.text }}</div>

    <!-- 统计卡 -->
    <div v-if="stats" class="stat-grid">
      <div class="stat-card">
        <div class="stat-num">{{ stats.total }}</div>
        <div class="stat-label">近 7 日总操作</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ statusOk }}</div>
        <div class="stat-label">成功 (success)</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ statusFail }}</div>
        <div class="stat-label">失败 (failure)</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ eventTypeCount }}</div>
        <div class="stat-label">事件类型</div>
      </div>
    </div>

    <!-- 筛选区 -->
    <div class="filter-card">
      <div class="form-row">
        <select v-model="filters.event_type" class="field" @change="loadLogs">
          <option value="">全部事件类型</option>
          <option v-for="t in eventTypes" :key="t" :value="t">{{ t }}</option>
        </select>
        <select v-model="filters.status" class="field" @change="loadLogs">
          <option value="">全部状态</option>
          <option value="success">成功</option>
          <option value="failure">失败</option>
        </select>
        <input
          v-model="filters.username"
          class="field"
          placeholder="操作人用户名"
          @keyup.enter="loadLogs"
        />
        <input
          v-model="filters.keyword"
          class="field grow"
          placeholder="关键词（路径/详情/操作）"
          @keyup.enter="loadLogs"
        />
        <input v-model="filters.start_time" class="field" type="date" @change="loadLogs" />
        <span class="hint">~</span>
        <input v-model="filters.end_time" class="field" type="date" @change="loadLogs" />
        <button class="btn primary" @click="loadLogs" :disabled="loading">查询</button>
        <button class="btn ghost" @click="resetFilters">重置</button>
      </div>
    </div>

    <!-- 日志表格 -->
    <div class="section">
      <div class="section-head">
        <h3>操作记录 <small>共 {{ page.total }} 条</small></h3>
        <span class="hint">按时间倒序展示</span>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>事件类型</th>
              <th>操作</th>
              <th>操作人</th>
              <th>状态</th>
              <th>方法</th>
              <th>路径</th>
              <th>IP</th>
              <th>详情</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading && !page.items.length">
              <td colspan="9" class="empty">加载中…</td>
            </tr>
            <tr v-else-if="!page.items.length">
              <td colspan="9" class="empty">暂无审计记录</td>
            </tr>
            <tr v-for="item in page.items" :key="item.id">
              <td class="mono">{{ formatDate(item.created_at) }}</td>
              <td><span class="chip">{{ item.event_type }}</span></td>
              <td>{{ item.action || '-' }}</td>
              <td>{{ item.username || '-' }}</td>
              <td>
                <span :class="['status', item.status === 'success' ? 'ok' : 'fail']">
                  {{ item.status }}
                </span>
              </td>
              <td class="mono">{{ item.method || '-' }}</td>
              <td class="mono path">{{ item.path || '-' }}</td>
              <td class="mono">{{ item.client_ip || '-' }}</td>
              <td class="detail-cell" :title="item.detail || ''">{{ item.detail || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div v-if="page.total > 0" class="pager">
        <span class="hint">第 {{ page.page }} / {{ totalPages }} 页 · 每页 {{ page.page_size }} 条</span>
        <div class="pager-btns">
          <button class="btn ghost" :disabled="page.page <= 1 || loading" @click="goPage(page.page - 1)">上一页</button>
          <button class="btn ghost" :disabled="page.page >= totalPages || loading" @click="goPage(page.page + 1)">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import {
  fetchAuditLogs,
  fetchAuditStats,
  fetchAuditEventTypes,
  purgeAuditLogs,
  type AuditLogPage,
  type AuditStats,
} from '../api/audit'

/** 状态 */
const loading = ref(false)
const purging = ref(false)
const msg = reactive({ text: '', type: '' })
const eventTypes = ref<string[]>([])
const stats = ref<AuditStats | null>(null)
const page = reactive<AuditLogPage>({ total: 0, page: 1, page_size: 20, items: [] })

const filters = reactive({
  event_type: '',
  status: '',
  username: '',
  keyword: '',
  start_time: '',
  end_time: '',
})

/** 计算 */
const totalPages = computed(() =>
  Math.max(1, Math.ceil(page.total / page.page_size))
)
const eventTypeCount = computed(() => (stats.value ? Object.keys(stats.value.by_event_type).length : 0))
const statusOk = computed(() => (stats.value?.by_status.success ?? 0))
const statusFail = computed(() => (stats.value?.by_status.failure ?? 0))

/** 工具 */
function flash(text: string, type = 'ok') {
  msg.text = text
  msg.type = type
  window.setTimeout(() => {
    msg.text = ''
  }, 3000)
}

function formatDate(v?: string | null): string {
  if (!v) return '-'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

/** 数据加载 */
async function loadStats() {
  try {
    stats.value = (await fetchAuditStats(7)).data
  } catch {
    stats.value = null
  }
}

async function loadEventTypes() {
  try {
    eventTypes.value = (await fetchAuditEventTypes()).data
  } catch {
    eventTypes.value = []
  }
}

async function loadLogs() {
  loading.value = true
  try {
    const res = (await fetchAuditLogs({
      event_type: filters.event_type || undefined,
      status: filters.status || undefined,
      username: filters.username || undefined,
      keyword: filters.keyword || undefined,
      start_time: filters.start_time || undefined,
      end_time: filters.end_time || undefined,
      page: page.page,
      page_size: page.page_size,
    })).data
    page.total = res.total
    page.page = res.page
    page.page_size = res.page_size
    page.items = res.items
  } catch (e) {
    flash(`加载审计日志失败：${(e as Error).message}`, 'error')
  } finally {
    loading.value = false
  }
}

function goPage(p: number) {
  if (p < 1 || p > totalPages.value) return
  page.page = p
  loadLogs()
}

function resetFilters() {
  filters.event_type = ''
  filters.status = ''
  filters.username = ''
  filters.keyword = ''
  filters.start_time = ''
  filters.end_time = ''
  page.page = 1
  loadLogs()
}

async function loadAll() {
  await Promise.all([loadStats(), loadEventTypes()])
  await loadLogs()
}

async function confirmPurge() {
  const ok = window.confirm('确定清理过期审计日志？该操作不可恢复。')
  if (!ok) return
  purging.value = true
  try {
    await purgeAuditLogs()
    flash('已清理过期审计日志')
    await loadAll()
  } catch (e) {
    flash(`清理失败：${(e as Error).message}`, 'error')
  } finally {
    purging.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.audit-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 页面头 */
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}
.page-head h2 {
  margin: 0;
  font-size: 20px;
  color: var(--color-text);
}
.page-head .sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-muted);
}
.head-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.badge {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--color-primary-light);
  color: var(--color-primary);
  border: 1px solid var(--color-primary-border);
  font-family: var(--font-mono, monospace);
}

/* 按钮 */
.btn {
  font-size: 13px;
  padding: 6px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-bg-subtle);
  color: var(--color-text);
  cursor: pointer;
  transition: background var(--transition-fast, 0.15s);
}
.btn:hover:not(:disabled) {
  background: var(--color-bg-hover);
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn.primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--color-text-on-primary, #fff);
}
.btn.danger {
  background: var(--color-error);
  border-color: var(--color-error);
  color: var(--color-text-on-primary, #fff);
}
.btn.ghost {
  background: transparent;
}

/* 消息 */
.msg {
  padding: 8px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
}
.msg.ok {
  background: var(--color-success-light, var(--color-bg-subtle));
  color: var(--color-success);
  border: 1px solid var(--color-success);
}
.msg.error {
  background: var(--color-error-light, var(--color-bg-subtle));
  color: var(--color-error);
  border: 1px solid var(--color-error);
}

/* 统计卡 */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}
.stat-card {
  background: var(--color-bg-subtle);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat-num {
  font-size: 24px;
  line-height: 1.1;
  color: var(--color-text);
}
.stat-label {
  font-size: 12px;
  color: var(--color-text-muted);
}

/* 筛选 */
.filter-card {
  background: var(--color-bg-subtle);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 12px 14px;
}
.form-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.field {
  font-size: 13px;
  padding: 6px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text);
  min-width: 120px;
}
.field.grow {
  flex: 1;
  min-width: 160px;
}
.hint {
  font-size: 12px;
  color: var(--color-text-muted);
}

/* 表格 */
.section {
  background: var(--color-bg-subtle);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 14px;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.section-head h3 {
  margin: 0;
  font-size: 15px;
  color: var(--color-text);
}
.section-head small {
  font-size: 12px;
  color: var(--color-text-muted);
}
.table-wrap {
  overflow-x: auto;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.data-table th,
.data-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid var(--color-border-light);
  color: var(--color-text);
  white-space: nowrap;
}
.data-table th {
  font-size: 12px;
  color: var(--color-text-muted);
  background: var(--color-bg-hover);
}
.data-table .mono {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
}
.data-table .path {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.data-table .detail-cell {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chip {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--color-primary-light);
  color: var(--color-primary);
  border: 1px solid var(--color-primary-border);
}
.status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: var(--radius-full);
}
.status.ok {
  background: var(--color-success-light, var(--color-bg-subtle));
  color: var(--color-success);
}
.status.fail {
  background: var(--color-error-light, var(--color-bg-subtle));
  color: var(--color-error);
}
.empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--color-text-muted);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
  font-size: 13px;
}

/* 分页 */
.pager {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  flex-wrap: wrap;
  gap: 8px;
}
.pager-btns {
  display: flex;
  gap: 8px;
}
</style>
