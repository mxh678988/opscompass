<script setup lang="ts">
// AI 治理台：决策分级授权（三级）/ 一键叫停 / 还原 / 全过程追溯
import { computed, onMounted, reactive, ref } from 'vue'

import {
  fetchActionTrace,
  fetchActions,
  fetchDecisionBoard,
  fetchInsights,
  restoreAction,
  revokeAction,
  setActionDecisionLevel,
  type ActionItem,
  type DecisionBoard,
  type DecisionTrace,
  type Insight,
} from '@/api/ai'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

const board = ref<DecisionBoard | null>(null)
const actions = ref<ActionItem[]>([])
const insights = ref<Insight[]>([])
const trace = ref<DecisionTrace | null>(null)

const loading = reactive({ board: false, actions: false, insights: false, trace: false })
const busyId = ref<number | null>(null)
const msg = reactive({ type: '', text: '' })

const filter = reactive({ status: '', handler: '', data_level: '', limit: 20, offset: 0 })
const total = ref(0)
const page = ref(1)

const PAGE_OPTIONS = [10, 20, 50, 100]

/** 操作人取自当前登录账号，缺省回落 admin */
const operator = computed(() => auth.user?.username || 'admin')

const LEVEL_TAG: Record<string, string> = {
  user_only: 'muted',
  user_authorized: 'warn',
  agent_autonomous: 'ok',
}

const LEVEL_LABEL: Record<string, string> = {
  user_only: '仅用户决策',
  user_authorized: '需用户授权',
  agent_autonomous: '智能体自主',
}

const STATUS_LABEL: Record<string, string> = {
  pending: '待处理',
  auto_executed: '已自主执行',
  approved: '已批准',
  rejected: '已驳回',
  executed: '已执行',
  failed: '执行失败',
  revoked: '已叫停',
}

const STATUS_OPTIONS = Object.keys(STATUS_LABEL)

const countOf = (code: string) => Number(board.value?.counts?.[code] ?? 0)

// ---- 洞察分页状态
const insightPage = ref(1)
const insightTotal = ref(0)
const insightFilter = reactive({ status: '', severity: '', limit: 20 })

async function loadInsights() {
  loading.insights = true
  try {
    const offset = (insightPage.value - 1) * insightFilter.limit
    const res = await fetchInsights({
      status: insightFilter.status || undefined,
      severity: insightFilter.severity || undefined,
      limit: Number(insightFilter.limit) || 20,
      offset,
    })
    const data = res.data
    insights.value = data?.items ?? []
    insightTotal.value = data?.total ?? 0
  } catch (e) {
    tip('error', `洞察加载失败：${errText(e)}`)
  } finally {
    loading.insights = false
  }
}

function goInsightPage(n: number) {
  insightPage.value = n
  loadInsights()
}

function prevInsightPage() {
  if (insightPage.value > 1) goInsightPage(insightPage.value - 1)
}

function nextInsightPage() {
  if (insightPage.value * insightFilter.limit < insightTotal.value) goInsightPage(insightPage.value + 1)
}

const insightStatusOptions = ['new', 'routed', 'resolved', 'dismissed']
const insightSeverityOptions = ['info', 'warning', 'critical']

function tip(type: string, text: string) {
  msg.type = type
  msg.text = text
}

function errText(e: any): string {
  return e?.response?.data?.message || e?.response?.data?.detail || e?.message || '请求失败'
}

function dt(v?: string | null) {
  return v ? String(v).replace('T', ' ').slice(0, 19) : '-'
}

function levelText(v?: string | null) {
  if (!v) return '-'
  return `${LEVEL_LABEL[v] ?? v}（${v}）`
}

async function loadBoard() {
  loading.board = true
  try {
    const res = await fetchDecisionBoard()
    board.value = res.data
  } catch (e) {
    tip('error', `治理看板加载失败：${errText(e)}`)
  } finally {
    loading.board = false
  }
}

async function loadActions() {
  loading.actions = true
  try {
    const offset = (page.value - 1) * filter.limit
    const res = await fetchActions({
      status: filter.status || undefined,
      handler: filter.handler || undefined,
      data_level: filter.data_level || undefined,
      limit: Number(filter.limit) || 20,
      offset,
    })
    const data = res.data
    actions.value = data?.items ?? []
    total.value = data?.total ?? 0
  } catch (e) {
    tip('error', `处置单加载失败：${errText(e)}`)
  } finally {
    loading.actions = false
  }
}

function goPage(n: number) {
  page.value = n
  loadActions()
}

function prevPage() {
  if (page.value > 1) goPage(page.value - 1)
}

function nextPage() {
  if (page.value * filter.limit < total.value) goPage(page.value + 1)
}

async function refreshAll() {
  tip('', '')
  await Promise.all([loadBoard(), loadActions(), loadInsights()])
}

async function openTrace(row: ActionItem) {
  loading.trace = true
  try {
    const res = await fetchActionTrace(row.id)
    trace.value = res.data
  } catch (e) {
    tip('error', `追溯加载失败：${errText(e)}`)
  } finally {
    loading.trace = false
  }
}

async function changeLevel(row: ActionItem, level: string) {
  if (!level || level === row.decision_level) return
  busyId.value = row.id
  try {
    const res = await setActionDecisionLevel(row.id, {
      operator: operator.value,
      decision_level: level,
      note: '治理台手动调整',
    })
    row.decision_level = res.data.decision_level
    row.decision_source = res.data.decision_source
    tip('ok', `处置单 #${row.id} 决策分级已调整为 ${levelText(res.data.decision_level)}`)
    await loadBoard()
  } catch (e) {
    tip('error', `调整分级失败：${errText(e)}`)
  } finally {
    busyId.value = null
  }
}

async function doRevoke(row: ActionItem) {
  const reason = window.prompt(`叫停处置单 #${row.id}（${row.title}）的理由：`, '风险复核，暂停执行')
  if (reason === null) return
  busyId.value = row.id
  try {
    const res = await revokeAction(row.id, { operator: operator.value, reason })
    Object.assign(row, res.data)
    tip('warn', `处置单 #${row.id} 已叫停，原状态 ${res.data.prev_status ?? '-'} 已留痕可还原`)
    await Promise.all([loadBoard(), loadActions()])
  } catch (e) {
    tip('error', `叫停失败：${errText(e)}`)
  } finally {
    busyId.value = null
  }
}

async function doRestore(row: ActionItem) {
  busyId.value = row.id
  try {
    const res = await restoreAction(row.id, { operator: operator.value, note: '治理台还原' })
    Object.assign(row, res.data)
    tip('ok', `处置单 #${row.id} 已还原至 ${STATUS_LABEL[res.data.status] ?? res.data.status}`)
    await Promise.all([loadBoard(), loadActions()])
  } catch (e) {
    tip('error', `还原失败：${errText(e)}`)
  } finally {
    busyId.value = null
  }
}

onMounted(refreshAll)
</script>

<template>
  <main class="ai-governance">
    <div class="page-head">
      <div>
        <h2>AI 治理台</h2>
        <p class="sub">
          决策分级授权三级可控，处置单支持一键叫停、还原与全过程追溯；操作人 {{ operator }}。
        </p>
      </div>
      <div class="head-actions">
        <button type="button" :disabled="loading.board || loading.actions" @click="refreshAll">
          刷新
        </button>
      </div>
    </div>

    <p v-if="msg.text" class="msg" :class="msg.type">{{ msg.text }}</p>

    <!-- 决策分级看板 -->
    <section class="panel">
      <div class="panel-title">
        决策分级看板
        <small v-if="board">共 {{ (board.levels ?? []).length }} 档授权级别</small>
      </div>
      <div class="level-grid">
        <div v-for="lv in board?.levels ?? []" :key="lv.code" class="level-card">
          <div class="level-head">
            <span class="tag" :class="LEVEL_TAG[lv.code] ?? 'muted'">{{ lv.name }}</span>
            <span class="mono code">{{ lv.code }}</span>
          </div>
          <p class="level-desc">{{ lv.desc }}</p>
          <div class="level-meta">
            <span>顺序 {{ lv.order }}</span>
            <span>{{ lv.auto_execute ? '可自主执行' : '不自主执行' }}</span>
            <span>{{ lv.need_approval ? '需人工审批' : '无需审批' }}</span>
          </div>
          <div class="level-count">
            <em>{{ countOf(lv.code) }}</em>
            <span>条处置单</span>
          </div>
        </div>
      </div>
      <div v-if="board" class="stat-row">
        <div class="stat"><em>{{ board.pending_total }}</em><span>待人工处理</span></div>
        <div class="stat"><em>{{ board.auto_executed_total }}</em><span>已自主执行</span></div>
        <div class="stat"><em>{{ board.revoked_total }}</em><span>已叫停</span></div>
        <div class="stat"><em>{{ board.sim_mode_total }}</em><span>仿真模式</span></div>
      </div>
    </section>

    <!-- AI 洞察列表 -->
    <section class="panel">
      <div class="panel-title">
        AI 洞察
        <small>共 {{ insightTotal }} 条</small>
      </div>
      <div class="filters">
        <label>
          <span>状态</span>
          <select v-model="insightFilter.status" @change="insightPage = 1; loadInsights()">
            <option value="">全部</option>
            <option v-for="s in insightStatusOptions" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>
          <span>严重度</span>
          <select v-model="insightFilter.severity" @change="insightPage = 1; loadInsights()">
            <option value="">全部</option>
            <option v-for="s in insightSeverityOptions" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>
          <span>条数</span>
          <select v-model.number="insightFilter.limit" @change="insightPage = 1; loadInsights()">
            <option v-for="n in PAGE_OPTIONS" :key="n" :value="n">{{ n }}</option>
          </select>
        </label>
        <button
          type="button"
          :disabled="loading.insights"
          @click="insightFilter.status = ''; insightFilter.severity = ''; insightPage = 1; loadInsights()"
        >
          重置
        </button>
      </div>

      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>标题</th>
              <th>类别</th>
              <th>严重度</th>
              <th>数据级别</th>
              <th>状态</th>
              <th>生成时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in insights" :key="row.id">
              <td class="mono">{{ row.id }}</td>
              <td class="ellipsis" :title="row.detail || row.title">{{ row.title }}</td>
              <td>{{ row.category || '-' }}</td>
              <td>
                <span class="tag" :class="row.severity === 'critical' ? 'bad' : row.severity === 'warning' ? 'warn' : 'muted'">
                  {{ row.severity || '-' }}
                </span>
              </td>
              <td class="mono">{{ row.data_level || '-' }}</td>
              <td>{{ row.status || '-' }}</td>
              <td class="mono small">{{ dt(row.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="!insights.length && !loading.insights" class="empty">暂无洞察数据</p>

      <div v-if="insights.length" class="pagination">
        <button type="button" :disabled="insightPage <= 1" @click="prevInsightPage">上一页</button>
        <span class="page-info">
          {{ insightTotal }} 条 / 共 {{ Math.ceil(insightTotal / insightFilter.limit) || 1 }} 页（第 {{ insightPage }} 页）
        </span>
        <button
          type="button"
          :disabled="insightPage * insightFilter.limit >= insightTotal"
          @click="nextInsightPage"
        >
          下一页
        </button>
      </div>
    </section>

    <!-- 处置单治理列表 -->
    <section class="panel">
      <div class="panel-title">
        处置单治理
        <small>共 {{ total }} 条</small>
      </div>
      <div class="filters">
        <label>
          <span>状态</span>
          <select v-model="filter.status" @change="page = 1; loadActions()">
            <option value="">全部</option>
            <option v-for="s in STATUS_OPTIONS" :key="s" :value="s">
              {{ STATUS_LABEL[s] }}（{{ s }}）
            </option>
          </select>
        </label>
        <label>
          <span>处理方</span>
          <select v-model="filter.handler" @change="page = 1; loadActions()">
            <option value="">全部</option>
            <option value="human">人工</option>
            <option value="ai">智能体</option>
          </select>
        </label>
        <label>
          <span>数据级别</span>
          <select v-model="filter.data_level" @change="page = 1; loadActions()">
            <option value="">全部</option>
            <option v-for="lv in ['L1', 'L2', 'L3', 'L4']" :key="lv" :value="lv">{{ lv }}</option>
          </select>
        </label>
        <label>
          <span>条数</span>
          <select v-model.number="filter.limit" @change="filter.limit = PAGE_OPTIONS.includes(filter.limit) ? filter.limit : 20; page = 1; loadActions()">
            <option v-for="n in PAGE_OPTIONS" :key="n" :value="n">{{ n }}</option>
          </select>
        </label>
        <button type="button" :disabled="loading.actions" @click="filter.status=''; filter.handler=''; filter.data_level=''; page=1; loadActions()">重置</button>
      </div>

      <div v-if="actions.length" class="pagination">
        <button type="button" :disabled="page <= 1" @click="prevPage">上一页</button>
        <span class="page-info">{{ total }} 条 / 共 {{ Math.ceil(total / filter.limit) || 1 }} 页（第 {{ page }} 页）</span>
        <button type="button" :disabled="page * filter.limit >= total" @click="nextPage">下一页</button>
      </div>

      <p v-if="loading.actions && !actions.length" class="empty">加载中…</p>
      <p v-else-if="!actions.length" class="empty">暂无处置单</p>
      <div v-else class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>标题</th>
              <th>类型</th>
              <th>数据级别</th>
              <th>严重度</th>
              <th>决策分级</th>
              <th>决策来源</th>
              <th>状态</th>
              <th>叫停</th>
              <th>创建时间</th>
              <th>治理操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in actions" :key="row.id">
              <td class="mono">{{ row.id }}</td>
              <td class="ellipsis" :title="row.title">{{ row.title }}</td>
              <td>{{ row.action_type || '-' }}</td>
              <td class="mono">{{ row.data_level || '-' }}</td>
              <td>{{ row.severity || '-' }}</td>
              <td>
                <select
                  class="level-select"
                  :value="row.decision_level"
                  :disabled="busyId === row.id"
                  @change="changeLevel(row, ($event.target as HTMLSelectElement).value)"
                >
                  <option v-for="(label, code) in LEVEL_LABEL" :key="code" :value="code">
                    {{ label }}
                  </option>
                </select>
              </td>
              <td>
                <span class="tag" :class="row.decision_source === 'manual' ? 'warn' : 'muted'">
                  {{ row.decision_source || '-' }}
                </span>
              </td>
              <td>
                <span class="tag" :class="row.status === 'revoked' ? 'bad' : row.status === 'pending' ? 'warn' : 'ok'">
                  {{ STATUS_LABEL[row.status] ?? row.status }}
                </span>
              </td>
              <td>
                <span v-if="row.revoked" class="tag bad" :title="row.revoke_reason || ''">
                  已叫停
                </span>
                <span v-else class="muted">-</span>
              </td>
              <td class="mono small">{{ dt(row.created_at) }}</td>
              <td class="ops">
                <button type="button" class="mini" @click="openTrace(row)">追溯</button>
                <button
                  v-if="!row.revoked"
                  type="button"
                  class="mini danger"
                  :disabled="busyId === row.id"
                  @click="doRevoke(row)"
                >
                  叫停
                </button>
                <button
                  v-else
                  type="button"
                  class="mini"
                  :disabled="busyId === row.id"
                  @click="doRestore(row)"
                >
                  还原
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 决策全过程追溯 -->
    <section class="panel">
      <div class="panel-title">
        决策全过程追溯
        <small v-if="trace">处置单 #{{ trace.action.id }} · {{ trace.action.title }}</small>
        <button
          v-if="trace"
          type="button"
          class="mini close"
          @click="trace = null"
        >
          收起
        </button>
      </div>
      <p v-if="loading.trace" class="empty">追溯加载中…</p>
      <p v-else-if="!trace" class="empty">点击列表中「追溯」查看某条处置单的全链路留痕</p>
      <template v-else>
        <div class="trace-summary">
          <span>决策分级 <b>{{ levelText(trace.action.decision_level) }}</b></span>
          <span>决策来源 <b>{{ trace.action.decision_source || '-' }}</b></span>
          <span>当前状态 <b>{{ STATUS_LABEL[trace.action.status] ?? trace.action.status }}</b></span>
          <span>叫停 <b>{{ trace.action.revoked ? '是' : '否' }}</b></span>
          <span v-if="trace.action.revoked">叫停人 <b>{{ trace.action.revoked_by || '-' }}</b></span>
          <span v-if="trace.action.revoked">叫停理由 <b>{{ trace.action.revoke_reason || '-' }}</b></span>
        </div>
        <ol class="trace-list">
          <li v-for="step in trace.trace" :key="step.seq">
            <span class="seq mono">{{ step.seq }}</span>
            <div class="step-body">
              <div class="step-head">
                <span class="tag" :class="step.actor_type === 'human' ? 'warn' : 'muted'">
                  {{ step.actor_type }}
                </span>
                <b>{{ step.action }}</b>
                <span class="mono small">{{ step.actor || '-' }}</span>
                <span class="mono small">{{ dt(step.at) }}</span>
              </div>
              <div class="step-detail">
                <span v-if="step.from_state || step.to_state" class="mono">
                  {{ step.from_state || '∅' }} → {{ step.to_state || '∅' }}
                </span>
                <span v-if="step.detail">{{ step.detail }}</span>
              </div>
            </div>
          </li>
        </ol>
      </template>
    </section>
  </main>
</template>

<style scoped>
.ai-governance {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 32px;
  max-width: 1400px;
  margin: 0 auto;
}
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.page-head h2 {
  margin: 0 0 4px;
  font-size: 20px;
  color: var(--color-text);
}
.page-head .sub {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.msg {
  margin: 0;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  border-left: 3px solid var(--color-border);
  background: var(--color-bg-subtle);
}
.msg.ok {
  border-left-color: var(--color-success);
  color: var(--color-success);
}
.msg.warn {
  border-left-color: var(--color-warning);
  color: var(--color-warning);
}
.msg.error {
  border-left-color: var(--color-error);
  color: var(--color-error);
}
.panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 20px;
  background: var(--color-bg);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.panel:hover {
  border-color: var(--color-primary-border);
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 14px;
}
.panel-title small {
  font-weight: 400;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.level-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}
.level-card {
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.level-card:hover {
  border-color: var(--color-primary-border);
  box-shadow: var(--shadow-sm);
}
.level-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.level-desc {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}
.level-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  font-size: 12px;
  color: var(--color-text-muted);
}
.level-count {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 2px;
}
.level-count em {
  font-style: normal;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-primary);
}
.level-count span {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.stat-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.stat {
  flex: 1 1 120px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--color-bg-subtle);
  text-align: center;
}
.stat em {
  display: block;
  font-style: normal;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-primary);
}
.stat span {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: flex-end;
  margin-bottom: 12px;
}
.filters label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
  min-width: 150px;
}
.filters input,
.filters select {
  width: 100%;
}
button {
  padding: 8px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 13px;
  transition: background var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast);
}
button:hover:not(:disabled) {
  border-color: var(--color-primary-border);
  color: var(--color-primary);
  background: var(--color-primary-light);
}
button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
button.mini {
  padding: 4px 10px;
  font-size: 12px;
}
button.mini.danger {
  color: var(--color-error);
  border-color: var(--color-error-border);
  background: var(--color-error-light);
}
button.mini.danger:hover:not(:disabled) {
  border-color: var(--color-error);
  color: var(--color-error);
  background: var(--color-error-light);
}
button.mini.close {
  margin-left: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th,
td {
  text-align: left;
  padding: 9px 8px;
  border-bottom: 1px solid var(--color-border-light);
  vertical-align: middle;
}
th {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: var(--color-bg-subtle);
  white-space: nowrap;
}
tbody tr:hover td {
  background: var(--color-bg-hover);
}
.mono {
  font-family: var(--font-mono);
}
.small {
  font-size: 11px;
  color: var(--color-text-muted);
}
.muted {
  color: var(--color-text-muted);
}
.ellipsis {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.code {
  font-size: 11px;
  color: var(--color-text-muted);
}
.level-select {
  padding: 4px 8px;
  font-size: 12px;
}
.ops {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.tag {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  background: var(--color-bg-subtle);
  color: var(--color-text-muted);
}
.tag.ok {
  background: var(--color-success-light);
  color: var(--color-success);
}
.tag.warn {
  background: var(--color-warning-light);
  color: var(--color-warning);
}
.tag.bad {
  background: var(--color-error-light);
  color: var(--color-error);
}
.empty {
  color: var(--color-text-muted);
  font-size: 13px;
  margin: 6px 0;
}
.trace-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
}
.trace-summary b {
  color: var(--color-text);
  font-weight: 600;
}
.trace-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.trace-list li {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--color-border-light);
}
.seq {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  line-height: 24px;
  text-align: center;
  border-radius: 50%;
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
}
.step-body {
  flex: 1;
  min-width: 0;
}
.step-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
}
.step-detail {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
  word-break: break-word;
}

/* ===== 分页 ===== */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0 0;
  border-top: 1px solid var(--color-border-light);
  font-size: 13px;
}
.pagination button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.page-info {
  color: var(--color-text-secondary);
}

/* ===== 响应式自适应（窗口缩放） ===== */
@media (max-width: 1024px) {
  .ai-governance {
    padding: 20px 16px;
  }
}
@media (max-width: 768px) {
  .ai-governance {
    padding: 16px 12px;
  }
  .panel {
    padding: 16px;
  }
  .filters label {
    min-width: 0;
    flex: 1 1 100%;
  }
  .ellipsis {
    max-width: 150px;
  }
}
@media (max-width: 480px) {
  .ai-governance {
    padding: 12px 10px;
  }
  .ellipsis {
    max-width: 110px;
  }
}
</style>
