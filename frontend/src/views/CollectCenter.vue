<script setup lang="ts">
// 采集调度中心：采集任务 / 手动执行 / 调度启停 / 运行记录
import { computed, onMounted, reactive, ref } from 'vue'

import {
  createCollectTask,
  deleteCollectTask,
  fetchCollectModes,
  fetchCollectOverview,
  fetchCollectRuns,
  fetchCollectSources,
  fetchCollectTasks,
  runCollectTask,
  scanCollectDue,
  toggleCollectTask,
  updateCollectTask,
  type CollectMode,
  type CollectOverview,
  type CollectRun,
  type CollectSource,
  type CollectTask,
  type CollectTaskPayload,
  type IngestMapping,
} from '@/api/collect'

/** 采集方式 / 状态 / 触发来源文案 */
const MODE_TEXT: Record<string, string> = {
  csv: '本地文件',
  api: 'HTTP 接口',
  sql: '数据库直连',
}

const STATUS_TEXT: Record<string, string> = {
  enabled: '启用中',
  paused: '已暂停',
}

const RUN_STATUS_TEXT: Record<string, string> = {
  success: '成功',
  failed: '失败',
  running: '执行中',
}

const TRIGGER_TEXT: Record<string, string> = {
  manual: '手动',
  schedule: '调度',
}

const GRANULARITY_OPTIONS = [
  { value: 'hour', label: '小时' },
  { value: 'day', label: '日' },
  { value: 'week', label: '周' },
  { value: 'month', label: '月' },
]

const overview = ref<CollectOverview | null>(null)
const modes = ref<CollectMode[]>([])
const sources = ref<CollectSource[]>([])
const tasks = ref<CollectTask[]>([])
const runs = ref<CollectRun[]>([])

const taskTotal = ref(0)
const runTotal = ref(0)
const taskPage = ref(1)
const taskPageSize = 20
const runPage = ref(1)
const runPageSize = 20

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const editingId = ref<number | null>(null)

const taskFilter = reactive({ status: '', collect_mode: '', keyword: '' })
const runFilter = reactive({ task_id: '' as string | number, status: '' })

const form = reactive({
  code: '',
  name: '',
  collect_mode: 'csv',
  source_id: '' as string | number,
  target: '',
  schedule_type: 'manual',
  interval_minutes: 60,
  status: 'enabled',
  remark: '',
  layout: 'wide' as 'wide' | 'long',
  time_column: '',
  time_format: '',
  granularity: 'day',
  metric_columns_text: '',
  metric_column: '',
  value_column: '',
  dim_columns_text: '',
  auto_create_metric: false,
  data_path: '',
  method: 'GET',
})

const currentMode = computed(() => modes.value.find((m) => m.mode === form.collect_mode) ?? null)
const maxTrend = computed(() => Math.max(1, ...(overview.value?.trend ?? []).map((p) => p.total)))
const modeDist = computed(() =>
  Object.entries(overview.value?.mode_distribution ?? {}).map(([mode, count]) => ({ mode, count })),
)
const isInterval = computed(() => form.schedule_type === 'interval')
const needsMapping = computed(() => form.collect_mode === 'csv' || form.collect_mode === 'api')

function modeText(mode: string): string {
  return MODE_TEXT[mode] ?? mode
}

function statusText(status: string): string {
  return STATUS_TEXT[status] ?? status
}

function runStatusText(status: string): string {
  return RUN_STATUS_TEXT[status] ?? status
}

function triggerText(trigger: string): string {
  return TRIGGER_TEXT[trigger] ?? trigger
}

function tagClass(status: string): string {
  if (status === 'enabled' || status === 'success') return 'ok'
  if (status === 'paused' || status === 'running') return 'warn'
  if (status === 'failed') return 'bad'
  return ''
}

function formatTime(value?: string | null): string {
  if (!value) return '—'
  return String(value).replace('T', ' ').slice(0, 19)
}

function detailText(value?: Record<string, unknown> | null): string {
  if (!value || !Object.keys(value).length) return ''
  try {
    return JSON.stringify(value)
  } catch {
    return ''
  }
}

function parseMetricColumns(text: string): Record<string, string> {
  const result: Record<string, string> = {}
  text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const parts = line.split(/[=:：]/)
      const code = (parts[0] ?? '').trim()
      const column = (parts.slice(1).join('=') ?? '').trim()
      if (code && column) result[code] = column
    })
  return result
}

function buildMapping(): IngestMapping | null {
  if (!form.time_column.trim()) return null
  const mapping: IngestMapping = {
    layout: form.layout,
    time_column: form.time_column.trim(),
    time_format: form.time_format.trim() || null,
    granularity: form.granularity,
    metric_columns: {},
    metric_column: null,
    value_column: null,
    dim_columns: [],
    auto_create_metric: form.auto_create_metric,
  }
  if (form.layout === 'wide') {
    mapping.metric_columns = parseMetricColumns(form.metric_columns_text)
  } else {
    mapping.metric_column = form.metric_column.trim() || null
    mapping.value_column = form.value_column.trim() || null
    mapping.dim_columns = form.dim_columns_text
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return mapping
}

function buildExtraConfig(): Record<string, unknown> {
  if (form.collect_mode !== 'api') return {}
  const config: Record<string, unknown> = { method: form.method }
  if (form.data_path.trim()) config.data_path = form.data_path.trim()
  return config
}

function resetForm() {
  Object.assign(form, {
    code: '',
    name: '',
    collect_mode: 'csv',
    source_id: '',
    target: '',
    schedule_type: 'manual',
    interval_minutes: 60,
    status: 'enabled',
    remark: '',
    layout: 'wide',
    time_column: '',
    time_format: '',
    granularity: 'day',
    metric_columns_text: '',
    metric_column: '',
    value_column: '',
    dim_columns_text: '',
    auto_create_metric: false,
    data_path: '',
    method: 'GET',
  })
  editingId.value = null
}

async function refreshTasks() {
  const res = await fetchCollectTasks({
    page: taskPage.value,
    page_size: taskPageSize,
    status: taskFilter.status || undefined,
    collect_mode: taskFilter.collect_mode || undefined,
    keyword: taskFilter.keyword.trim() || undefined,
  })
  tasks.value = res.data.items
  taskTotal.value = res.data.total
}

async function refreshRuns() {
  const res = await fetchCollectRuns({
    page: runPage.value,
    page_size: runPageSize,
    task_id: runFilter.task_id ? Number(runFilter.task_id) : undefined,
    status: runFilter.status || undefined,
  })
  runs.value = res.data.items
  runTotal.value = res.data.total
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [ov, md, sc] = await Promise.all([
      fetchCollectOverview(),
      fetchCollectModes(),
      fetchCollectSources(),
    ])
    overview.value = ov.data
    modes.value = md.data
    sources.value = sc.data
    await Promise.all([refreshTasks(), refreshRuns()])
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '加载失败'
  } finally {
    loading.value = false
  }
}

function searchTasks() {
  taskPage.value = 1
  refreshTasks().catch((e: any) => {
    error.value = e?.response?.data?.detail ?? '查询失败'
  })
}

function searchRuns() {
  runPage.value = 1
  refreshRuns().catch((e: any) => {
    error.value = e?.response?.data?.detail ?? '查询失败'
  })
}

function turnTaskPage(delta: number) {
  const next = taskPage.value + delta
  if (next < 1 || (next - 1) * taskPageSize >= taskTotal.value) return
  taskPage.value = next
  refreshTasks().catch(() => undefined)
}

function turnRunPage(delta: number) {
  const next = runPage.value + delta
  if (next < 1 || (next - 1) * runPageSize >= runTotal.value) return
  runPage.value = next
  refreshRuns().catch(() => undefined)
}

function buildPayload(): CollectTaskPayload {
  return {
    code: form.code.trim(),
    name: form.name.trim(),
    source_id: form.source_id ? Number(form.source_id) : null,
    collect_mode: form.collect_mode,
    target: form.target.trim(),
    mapping: buildMapping(),
    extra_config: buildExtraConfig(),
    schedule_type: form.schedule_type,
    interval_minutes: isInterval.value ? Number(form.interval_minutes) || 0 : 0,
    cron_expr: null,
    status: form.status,
    remark: form.remark.trim(),
  }
}

async function submitTask() {
  error.value = ''
  notice.value = ''
  if (!editingId.value && !form.code.trim()) {
    error.value = '任务编码必填（字母、数字、下划线与连字符）'
    return
  }
  if (!form.name.trim()) {
    error.value = '任务名称必填'
    return
  }
  if (!form.target.trim()) {
    error.value = '请填写采集目标（' + (currentMode.value?.target_label ?? '目标') + '）'
    return
  }
  if (isInterval.value && Number(form.interval_minutes) < 1) {
    error.value = '调度间隔至少 1 分钟'
    return
  }
  if (needsMapping.value && !form.time_column.trim()) {
    error.value = '请填写时间列名：本地文件与接口采集需字段映射才能写入指标'
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (editingId.value) {
      const body: Partial<CollectTaskPayload> = {
        name: payload.name,
        source_id: payload.source_id,
        collect_mode: payload.collect_mode,
        target: payload.target,
        mapping: payload.mapping,
        extra_config: payload.extra_config,
        schedule_type: payload.schedule_type,
        interval_minutes: payload.interval_minutes,
        status: payload.status,
        remark: payload.remark,
      }
      await updateCollectTask(editingId.value, body)
      notice.value = '采集任务已更新'
    } else {
      await createCollectTask(payload)
      notice.value = '采集任务已创建'
    }
    resetForm()
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '保存失败'
  } finally {
    saving.value = false
  }
}

function editTask(row: CollectTask) {
  editingId.value = row.id
  const mapping = row.mapping ?? null
  const metricColumns = (mapping?.metric_columns ?? {}) as Record<string, string>
  Object.assign(form, {
    code: row.code,
    name: row.name,
    collect_mode: row.collect_mode,
    source_id: row.source_id ?? '',
    target: row.target,
    schedule_type: row.schedule_type,
    interval_minutes: row.interval_minutes || 60,
    status: row.status,
    remark: row.remark ?? '',
    layout: mapping?.layout ?? 'wide',
    time_column: mapping?.time_column ?? '',
    time_format: mapping?.time_format ?? '',
    granularity: mapping?.granularity ?? 'day',
    metric_columns_text: Object.entries(metricColumns)
      .map(([code, column]) => code + '=' + column)
      .join('\n'),
    metric_column: mapping?.metric_column ?? '',
    value_column: mapping?.value_column ?? '',
    dim_columns_text: (mapping?.dim_columns ?? []).join(', '),
    auto_create_metric: Boolean(mapping?.auto_create_metric),
    data_path: String((row.extra_config?.data_path as string) ?? ''),
    method: String((row.extra_config?.method as string) ?? 'GET'),
  })
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function doRun(row: CollectTask) {
  error.value = ''
  notice.value = ''
  try {
    const res = await runCollectTask(row.id)
    const run = res.data
    notice.value =
      '「' + row.name + '」执行' + runStatusText(run.status) + '：写入 ' + run.rows_written + ' 行'
      + (run.simulated ? '（演练，未真实写入）' : '')
      + (run.message ? '｜' + run.message : '')
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '执行失败'
  }
}

async function doToggle(row: CollectTask) {
  try {
    const res = await toggleCollectTask(row.id)
    notice.value = '任务「' + row.name + '」已' + (res.data.status === 'enabled' ? '启用' : '暂停')
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '操作失败'
  }
}

async function removeTask(row: CollectTask) {
  if (!window.confirm('确认删除采集任务「' + row.name + '」？其运行记录将一并删除。')) return
  try {
    await deleteCollectTask(row.id)
    notice.value = '采集任务已删除'
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '删除失败'
  }
}

async function doScan() {
  error.value = ''
  notice.value = ''
  try {
    const res = await scanCollectDue()
    notice.value = '到期扫描完成：执行 ' + res.data.count + ' 个任务'
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '扫描失败'
  }
}

function fillFromMode(mode: CollectMode) {
  form.collect_mode = mode.mode
  if (mode.mode === 'sql') form.status = 'enabled'
}

onMounted(load)
</script>

<template>
  <section class="collect">
    <header class="page-head">
      <div>
        <h2>采集调度中心</h2>
        <p class="sub">外部数据采集任务的接入、映射、执行与运行留痕</p>
      </div>
      <div class="head-actions">
        <button class="btn ghost" @click="doScan">扫描到期任务</button>
        <button class="btn ghost" @click="load">刷新</button>
        <span class="sched-flag" :class="overview?.scheduler_enabled ? 'ok' : 'warn'">
          调度线程：{{ overview?.scheduler_enabled ? '运行中' : '未启用' }}
        </span>
      </div>
    </header>

    <p v-if="error" class="msg bad">{{ error }}</p>
    <p v-if="notice" class="msg ok">{{ notice }}</p>

    <div class="stats">
      <div class="stat">
        <span class="label">采集任务</span>
        <strong>{{ overview?.total_tasks ?? '—' }}</strong>
        <em>启用 {{ overview?.enabled_tasks ?? 0 }} / 暂停 {{ overview?.paused_tasks ?? 0 }}</em>
      </div>
      <div class="stat">
        <span class="label">执行次数</span>
        <strong>{{ overview?.total_runs ?? '—' }}</strong>
        <em>近 24h {{ overview?.runs_24h ?? 0 }} 次</em>
      </div>
      <div class="stat">
        <span class="label">近 24h 成功率</span>
        <strong>{{ overview ? overview.success_rate_24h + '%' : '—' }}</strong>
        <em>按近 24h 执行记录统计</em>
      </div>
      <div class="stat">
        <span class="label">近 24h 写入行</span>
        <strong>{{ overview?.rows_written_24h ?? '—' }}</strong>
        <em>真实落库行数</em>
      </div>
    </div>

    <div class="cols">
      <div class="card">
        <h3>采集方式</h3>
        <ul class="modes">
          <li
            v-for="mode in modes"
            :key="mode.mode"
            :class="{ active: form.collect_mode === mode.mode }"
            @click="fillFromMode(mode)"
          >
            <div class="mode-head">
              <b>{{ mode.name }}</b>
              <span class="tag" :class="mode.real_fetch ? 'ok' : 'warn'">
                {{ mode.real_fetch ? '真实写入' : '演练模式' }}
              </span>
            </div>
            <p class="mode-desc">{{ mode.description }}</p>
            <p class="mode-hint">目标：{{ mode.target_label }} · {{ mode.target_hint }}</p>
          </li>
          <li v-if="!modes.length" class="empty">暂无可用采集方式</li>
        </ul>
      </div>

      <div class="card">
        <h3>采集趋势（近 7 天）</h3>
        <div v-if="overview?.trend?.length" class="trend">
          <div v-for="point in overview.trend" :key="point.day" class="trend-col">
            <div class="bar-wrap">
              <div class="bar" :style="{ height: (point.total / maxTrend) * 100 + '%' }"></div>
            </div>
            <span class="trend-num">{{ point.total }}</span>
            <span class="trend-date">{{ point.day.slice(5) }}</span>
          </div>
        </div>
        <p v-else class="empty">暂无执行记录</p>

        <h3 class="mt">方式分布</h3>
        <ul class="dist">
          <li v-for="item in modeDist" :key="item.mode">
            <span>{{ modeText(item.mode) }}</span>
            <b>{{ item.count }}</b>
          </li>
          <li v-if="!modeDist.length" class="empty">暂无任务</li>
        </ul>
      </div>
    </div>

    <div class="card">
      <h3>{{ editingId ? '编辑采集任务 #' + editingId : '新建采集任务' }}</h3>
      <div class="form">
        <label>
          <span>任务编码 *</span>
          <input v-model="form.code" :disabled="!!editingId" placeholder="collect_sales_daily" />
        </label>
        <label>
          <span>任务名称 *</span>
          <input v-model="form.name" placeholder="门店销售日采集" />
        </label>
        <label>
          <span>采集方式</span>
          <select v-model="form.collect_mode">
            <option v-for="mode in modes" :key="mode.mode" :value="mode.mode">{{ mode.name }}</option>
          </select>
        </label>
        <label>
          <span>数据源</span>
          <select v-model="form.source_id">
            <option value="">不绑定数据源</option>
            <option v-for="source in sources" :key="source.id" :value="source.id">
              {{ source.name }}（{{ source.code }}）
            </option>
          </select>
        </label>
        <label class="wide">
          <span>采集目标 *（{{ currentMode?.target_label ?? '目标' }}）</span>
          <input v-model="form.target" :placeholder="currentMode?.target_hint ?? '采集目标'" />
        </label>
        <label>
          <span>调度方式</span>
          <select v-model="form.schedule_type">
            <option value="manual">手动触发</option>
            <option value="interval">定时循环</option>
          </select>
        </label>
        <label v-if="isInterval">
          <span>间隔（分钟）</span>
          <input v-model="form.interval_minutes" type="number" min="1" />
        </label>
        <label>
          <span>状态</span>
          <select v-model="form.status">
            <option value="enabled">启用中</option>
            <option value="paused">已暂停</option>
          </select>
        </label>
        <label class="wide">
          <span>备注</span>
          <input v-model="form.remark" placeholder="选填" />
        </label>
      </div>

      <template v-if="form.collect_mode === 'api'">
        <h4>接口参数</h4>
        <div class="form">
          <label>
            <span>请求方法</span>
            <select v-model="form.method">
              <option value="GET">GET</option>
              <option value="POST">POST</option>
            </select>
          </label>
          <label class="wide">
            <span>响应数据路径</span>
            <input v-model="form.data_path" placeholder="data.list，选填" />
          </label>
        </div>
      </template>

      <template v-if="needsMapping">
        <h4>字段映射（IngestMapping）</h4>
        <div class="form">
          <label>
            <span>布局</span>
            <select v-model="form.layout">
              <option value="wide">宽表（每列一个指标）</option>
              <option value="long">长表（指标名/值分列）</option>
            </select>
          </label>
          <label>
            <span>时间列 *</span>
            <input v-model="form.time_column" placeholder="stat_date" />
          </label>
          <label>
            <span>时间格式</span>
            <input v-model="form.time_format" placeholder="%Y-%m-%d，选填" />
          </label>
          <label>
            <span>时间粒度</span>
            <select v-model="form.granularity">
              <option v-for="opt in GRANULARITY_OPTIONS" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </label>
          <label v-if="form.layout === 'wide'" class="wide">
            <span>指标列映射（每行：指标编码=列名）</span>
            <textarea
              v-model="form.metric_columns_text"
              rows="4"
              placeholder="sales_amount=销售额&#10;order_count=订单数"
            ></textarea>
          </label>
          <template v-else>
            <label>
              <span>指标名列</span>
              <input v-model="form.metric_column" placeholder="metric_name" />
            </label>
            <label>
              <span>指标值列</span>
              <input v-model="form.value_column" placeholder="metric_value" />
            </label>
            <label class="wide">
              <span>维度列（逗号分隔）</span>
              <input v-model="form.dim_columns_text" placeholder="store_id, channel" />
            </label>
          </template>
          <label class="check">
            <input v-model="form.auto_create_metric" type="checkbox" />
            <span>指标不存在时自动创建</span>
          </label>
        </div>
      </template>

      <div class="form-actions">
        <button class="btn primary" :disabled="saving" @click="submitTask">
          {{ saving ? '提交中…' : editingId ? '保存修改' : '创建任务' }}
        </button>
        <button v-if="editingId" class="btn ghost" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h3>采集任务</h3>
        <div class="filters">
          <select v-model="taskFilter.status" @change="searchTasks">
            <option value="">全部状态</option>
            <option value="enabled">启用中</option>
            <option value="paused">已暂停</option>
          </select>
          <select v-model="taskFilter.collect_mode" @change="searchTasks">
            <option value="">全部方式</option>
            <option v-for="mode in modes" :key="mode.mode" :value="mode.mode">{{ mode.name }}</option>
          </select>
          <input
            v-model="taskFilter.keyword"
            placeholder="编码 / 名称 / 目标"
            @keyup.enter="searchTasks"
          />
          <button class="btn ghost" @click="searchTasks">查询</button>
        </div>
      </div>
      <div class="table-scroll">
      <table class="tbl">
        <thead>
          <tr>
            <th>编码</th>
            <th>名称</th>
            <th>方式</th>
            <th>目标</th>
            <th>调度</th>
            <th>状态</th>
            <th>上次执行</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in tasks" :key="row.id">
            <td class="mono">{{ row.code }}</td>
            <td>{{ row.name }}</td>
            <td><span class="tag">{{ modeText(row.collect_mode) }}</span></td>
            <td class="ellipsis" :title="row.target">{{ row.target }}</td>
            <td>{{ row.schedule_type === 'interval' ? '每 ' + row.interval_minutes + ' 分钟' : '手动' }}</td>
            <td><span class="tag" :class="tagClass(row.status)">{{ statusText(row.status) }}</span></td>
            <td>{{ formatTime(row.last_run_at) }}</td>
            <td class="ops">
              <button class="btn mini" @click="doRun(row)">执行</button>
              <button class="btn mini" @click="doToggle(row)">
                {{ row.status === 'enabled' ? '暂停' : '启用' }}
              </button>
              <button class="btn mini" @click="editTask(row)">编辑</button>
              <button class="btn mini danger" @click="removeTask(row)">删除</button>
            </td>
          </tr>
          <tr v-if="!tasks.length">
            <td colspan="8" class="empty">{{ loading ? '加载中…' : '暂无采集任务' }}</td>
          </tr>
        </tbody>
      </table>
      </div>
      <div class="pager">
        <button class="btn mini" :disabled="taskPage <= 1" @click="turnTaskPage(-1)">上一页</button>
        <span>第 {{ taskPage }} 页 / 共 {{ taskTotal }} 条</span>
        <button
          class="btn mini"
          :disabled="taskPage * taskPageSize >= taskTotal"
          @click="turnTaskPage(1)"
        >
          下一页
        </button>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h3>运行记录</h3>
        <div class="filters">
          <select v-model="runFilter.task_id" @change="searchRuns">
            <option value="">全部任务</option>
            <option v-for="row in tasks" :key="row.id" :value="row.id">{{ row.name }}</option>
          </select>
          <select v-model="runFilter.status" @change="searchRuns">
            <option value="">全部结果</option>
            <option value="success">成功</option>
            <option value="failed">失败</option>
            <option value="running">执行中</option>
          </select>
          <button class="btn ghost" @click="searchRuns">查询</button>
        </div>
      </div>
      <div class="table-scroll">
      <table class="tbl">
        <thead>
          <tr>
            <th>任务</th>
            <th>触发</th>
            <th>结果</th>
            <th>读取行</th>
            <th>写入行</th>
            <th>耗时(ms)</th>
            <th>开始时间</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in runs" :key="row.id">
            <td>{{ row.task_name ?? ('#' + row.task_id) }}</td>
            <td><span class="tag">{{ triggerText(row.trigger) }}</span></td>
            <td>
              <span class="tag" :class="tagClass(row.status)">{{ runStatusText(row.status) }}</span>
              <span v-if="row.simulated" class="tag warn">演练</span>
            </td>
            <td>{{ row.rows_in }}</td>
            <td>{{ row.rows_written }}</td>
            <td>{{ row.duration_ms }}</td>
            <td>{{ formatTime(row.started_at) }}</td>
            <td class="ellipsis" :title="row.message + ' ' + detailText(row.detail)">
              {{ row.message || detailText(row.detail) || '—' }}
            </td>
          </tr>
          <tr v-if="!runs.length">
            <td colspan="8" class="empty">{{ loading ? '加载中…' : '暂无运行记录' }}</td>
          </tr>
        </tbody>
      </table>
      </div>
      <div class="pager">
        <button class="btn mini" :disabled="runPage <= 1" @click="turnRunPage(-1)">上一页</button>
        <span>第 {{ runPage }} 页 / 共 {{ runTotal }} 条</span>
        <button
          class="btn mini"
          :disabled="runPage * runPageSize >= runTotal"
          @click="turnRunPage(1)"
        >
          下一页
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.collect {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 20px 60px;
  color: var(--color-text, #1f2329);
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.page-head h2 {
  margin: 0 0 6px;
  font-size: 22px;
}

.sub {
  margin: 0;
  font-size: 13px;
  color: var(--color-muted, #8a919f);
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.sched-flag {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--color-border, #e5e6eb);
  color: var(--color-muted, #8a919f);
}

.msg {
  margin: 0 0 12px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
}

.msg.ok {
  background: rgba(0, 180, 42, 0.1);
  color: #0a8a2a;
}

.msg.bad {
  background: rgba(245, 63, 63, 0.1);
  color: #c22b2b;
}

.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.stat {
  background: var(--color-card, #fff);
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stat .label {
  font-size: 13px;
  color: var(--color-muted, #8a919f);
}

.stat strong {
  font-size: 26px;
  line-height: 1.1;
}

.stat em {
  font-size: 12px;
  font-style: normal;
  color: var(--color-muted, #8a919f);
}

.cols {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

@media (max-width: 1000px) {
  .cols {
    grid-template-columns: minmax(0, 1fr);
  }
}

.card {
  background: var(--color-card, #fff);
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 10px;
  padding: 18px;
  margin-bottom: 16px;
}

.card h3 {
  margin: 0 0 14px;
  font-size: 16px;
}

.card h3.mt {
  margin-top: 22px;
}

.card h4 {
  margin: 18px 0 10px;
  font-size: 14px;
  color: var(--color-muted, #8a919f);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.card-head h3 {
  margin: 0;
}

.modes {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}

.modes li {
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 8px;
  padding: 12px 14px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.modes li:hover {
  border-color: var(--color-primary, #3370ff);
}

.modes li.active {
  border-color: var(--color-primary, #3370ff);
  background: rgba(51, 112, 255, 0.06);
}

.mode-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mode-desc {
  margin: 8px 0 4px;
  font-size: 13px;
  color: var(--color-text, #1f2329);
}

.mode-hint {
  margin: 0;
  font-size: 12px;
  color: var(--color-muted, #8a919f);
}

.trend {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  height: 160px;
  padding: 8px 4px 0;
}

.trend-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  height: 100%;
}

.bar-wrap {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.bar {
  width: 60%;
  min-height: 3px;
  border-radius: 4px 4px 0 0;
  background: var(--color-primary, #3370ff);
}

.trend-num {
  font-size: 12px;
}

.trend-date {
  font-size: 11px;
  color: var(--color-muted, #8a919f);
}

.dist {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.dist li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  border-bottom: 1px dashed var(--color-border, #e5e6eb);
  padding-bottom: 6px;
}

.form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px 16px;
}

.form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.form label.wide {
  grid-column: 1 / -1;
}

.form label span {
  color: var(--color-muted, #8a919f);
}

.form label.check {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

.form label.check span {
  color: var(--color-text, #1f2329);
}

input,
select,
textarea {
  font: inherit;
  font-size: 13px;
  color: var(--color-text, #1f2329);
  background: var(--color-bg, #f7f8fa);
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 6px;
  padding: 7px 10px;
  outline: none;
}

input:focus,
select:focus,
textarea:focus {
  border-color: var(--color-primary, #3370ff);
  background: #fff;
}

input:disabled {
  color: var(--color-muted, #8a919f);
  cursor: not-allowed;
}

textarea {
  resize: vertical;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.btn {
  font: inherit;
  font-size: 13px;
  border-radius: 6px;
  border: 1px solid var(--color-border, #e5e6eb);
  background: #fff;
  color: var(--color-text, #1f2329);
  padding: 7px 14px;
  cursor: pointer;
  transition: opacity 0.15s, border-color 0.15s;
}

.btn:hover {
  border-color: var(--color-primary, #3370ff);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.primary {
  background: var(--color-primary, #3370ff);
  border-color: var(--color-primary, #3370ff);
  color: #fff;
}

.btn.ghost {
  background: transparent;
}

.btn.mini {
  padding: 4px 10px;
  font-size: 12px;
}

.btn.danger {
  color: #c22b2b;
  border-color: rgba(245, 63, 63, 0.4);
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.tbl th,
.tbl td {
  text-align: left;
  padding: 9px 10px;
  border-bottom: 1px solid var(--color-border, #e5e6eb);
  vertical-align: middle;
}

.tbl th {
  font-weight: 600;
  color: var(--color-muted, #8a919f);
  white-space: nowrap;
}

.tbl .mono {
  font-family: Consolas, Menlo, monospace;
}

.tbl .ops {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.ellipsis {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag {
  display: inline-block;
  font-size: 12px;
  line-height: 1.6;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid var(--color-border, #e5e6eb);
  background: var(--color-bg, #f7f8fa);
  color: var(--color-muted, #8a919f);
  margin-right: 4px;
}

.tag.ok {
  color: #0a8a2a;
  border-color: rgba(0, 180, 42, 0.35);
  background: rgba(0, 180, 42, 0.1);
}

.tag.warn {
  color: #a8710a;
  border-color: rgba(255, 158, 0, 0.35);
  background: rgba(255, 158, 0, 0.12);
}

.tag.bad {
  color: #c22b2b;
  border-color: rgba(245, 63, 63, 0.35);
  background: rgba(245, 63, 63, 0.1);
}

.empty {
  text-align: center;
  color: var(--color-muted, #8a919f);
  font-size: 13px;
  padding: 14px 0;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 14px;
  font-size: 13px;
  color: var(--color-muted, #8a919f);
}

    /* ===== 响应式自适应（窗口缩放） ===== */
    .page-head {
      flex-wrap: wrap;
    }
    .pager {
      flex-wrap: wrap;
      justify-content: flex-start;
    }
    @media (max-width: 1024px) {
      .collect {
        padding: 20px 16px 48px;
      }
      .stats {
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      }
    }
    @media (max-width: 768px) {
      .collect {
        padding: 16px 12px 40px;
      }
      .page-head h2 {
        font-size: 19px;
      }
      .stats {
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      }
      .form {
        grid-template-columns: 1fr;
      }
      .ellipsis {
        max-width: 100%;
      }
      .card {
        padding: 14px;
      }
      .trend {
        height: 140px;
      }
    }
    @media (max-width: 480px) {
      .collect {
        padding: 14px 10px 32px;
      }
      .stats {
        grid-template-columns: 1fr;
      }
      .form-actions {
        flex-wrap: wrap;
      }
      .head-actions {
        width: 100%;
      }
    }
</style>
