<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  fetchImportTasks,
  fetchIngestFiles,
  loadSampleFile,
  previewIngestFile,
  runIngest,
  uploadIngestFile,
  type ImportTaskItem,
  type IngestPreview,
  type RawFileItem,
  type SampleFileItem,
} from '@/api/ingest'
import { fetchDataSources, type DataSourceItem } from '@/api/datasources'

const rawFiles = ref<RawFileItem[]>([])
const samples = ref<SampleFileItem[]>([])
const sources = ref<DataSourceItem[]>([])
const tasks = ref<ImportTaskItem[]>([])
const preview = ref<IngestPreview | null>(null)
const result = ref<ImportTaskItem | null>(null)

const currentFile = ref('')
const uploading = ref(false)
const previewing = ref(false)
const running = ref(false)
const error = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const mapping = reactive({
  layout: 'wide' as 'wide' | 'long',
  time_column: '',
  granularity: 'day',
  metric_column: '',
  value_column: '',
  dim_columns: [] as string[],
  source_code: '',
  auto_create_metric: false,
  pairs: [] as { code: string; column: string }[],
})

const columns = computed(() => preview.value?.columns ?? [])
const knownMetrics = computed(() => preview.value?.known_metrics ?? [])

async function loadFiles() {
  const res = await fetchIngestFiles()
  rawFiles.value = res.data.raw ?? []
  samples.value = res.data.samples ?? []
}

async function loadTasks() {
  try {
    const res = await fetchImportTasks({ page: 1, page_size: 10 })
    tasks.value = res.data.items ?? []
  } catch {
    tasks.value = []
  }
}

async function loadSources() {
  try {
    const res = await fetchDataSources({ page: 1, page_size: 100 })
    sources.value = res.data.items ?? []
  } catch {
    sources.value = []
  }
}

function applySuggested(p: IngestPreview) {
  const s = p.suggested
  mapping.layout = s.layout
  mapping.time_column = s.time_column || p.columns[0] || ''
  mapping.granularity = s.granularity || 'day'
  mapping.metric_column = s.metric_column ?? ''
  mapping.value_column = s.value_column ?? ''
  mapping.dim_columns = [...(s.dim_columns ?? [])]
  mapping.pairs = Object.entries(s.metric_columns ?? {}).map(([code, column]) => ({ code, column }))
  if (!mapping.pairs.length) addPair()
}

function addPair() {
  mapping.pairs.push({ code: '', column: columns.value[0] ?? '' })
}

function removePair(index: number) {
  mapping.pairs.splice(index, 1)
}

async function doPreview(fileName: string) {
  previewing.value = true
  error.value = ''
  result.value = null
  try {
    const res = await previewIngestFile({ file_name: fileName, limit: 20 })
    preview.value = res.data
    currentFile.value = fileName
    applySuggested(res.data)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '预览失败'
    preview.value = null
  } finally {
    previewing.value = false
  }
}

async function onUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    const res = await uploadIngestFile(file)
    await loadFiles()
    await doPreview(res.data.file_name)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '上传失败'
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function useSample(name: string) {
  error.value = ''
  try {
    await loadSampleFile(name)
    await loadFiles()
    await doPreview(name)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '载入示例失败'
  }
}

async function submit() {
  if (!currentFile.value) return
  error.value = ''
  if (!mapping.time_column) {
    error.value = '请选择时间列'
    return
  }
  const payload: any = {
    layout: mapping.layout,
    time_column: mapping.time_column,
    granularity: mapping.granularity,
    auto_create_metric: mapping.auto_create_metric,
  }
  if (mapping.layout === 'wide') {
    const pairs = mapping.pairs.filter((p) => p.code.trim() && p.column)
    if (!pairs.length) {
      error.value = '宽表模式至少需要一行「文件列 → 指标编码」映射'
      return
    }
    payload.metric_columns = Object.fromEntries(pairs.map((p) => [p.code.trim(), p.column]))
  } else {
    if (!mapping.metric_column || !mapping.value_column) {
      error.value = '长表模式需选择指标编码列与指标值列'
      return
    }
    payload.metric_column = mapping.metric_column
    payload.value_column = mapping.value_column
    payload.dim_columns = mapping.dim_columns
  }
  running.value = true
  try {
    const res = await runIngest({
      file_name: currentFile.value,
      source_code: mapping.source_code || null,
      mapping: payload,
    })
    result.value = res.data
    await loadTasks()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '导入失败'
  } finally {
    running.value = false
  }
}

function display(value: unknown): string {
  if (value === null || value === undefined) return ''
  return String(value)
}

onMounted(async () => {
  await Promise.all([loadFiles(), loadTasks(), loadSources()])
})
</script>

<template>
  <main class="data-import">
    <header class="head">
      <h1>数据导入</h1>
      <p class="subtitle">上传 CSV / Excel，选择列映射后写入指标仓库，形成「导入 → 清洗 → 入库 → 出指标」闭环</p>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section class="panel">
      <h2>1. 选择文件</h2>
      <div class="picker">
        <label class="upload">
          <input ref="fileInput" type="file" accept=".csv,.xlsx,.xls" @change="onUpload" />
          <span>{{ uploading ? '上传中…' : '上传本地文件' }}</span>
        </label>
        <span class="hint">支持 .csv / .xlsx / .xls，单文件不超过 20MB</span>
      </div>

      <div class="file-groups">
        <div class="file-group">
          <h3>服务端已存文件（data/raw）</h3>
          <ul>
            <li v-for="f in rawFiles" :key="f.file_name" :class="{ active: currentFile === f.file_name }">
              <span class="mono">{{ f.file_name }}</span>
              <span class="size">{{ (f.file_size / 1024).toFixed(1) }} KB</span>
              <button @click="doPreview(f.file_name)">预览</button>
            </li>
            <li v-if="!rawFiles.length" class="empty">暂无文件，请上传或载入示例</li>
          </ul>
        </div>
        <div class="file-group">
          <h3>内置示例数据</h3>
          <ul>
            <li v-for="f in samples" :key="f.file_name">
              <span class="mono">{{ f.file_name }}</span>
              <span class="size">{{ (f.file_size / 1024).toFixed(1) }} KB</span>
              <button @click="useSample(f.file_name)">载入并预览</button>
            </li>
            <li v-if="!samples.length" class="empty">示例目录为空</li>
          </ul>
        </div>
      </div>
    </section>

    <section v-if="preview" class="panel">
      <h2>2. 结构预览<span class="file-tag mono">{{ preview.file_name }}</span></h2>
      <p class="meta">
        共 {{ preview.total_rows }} 行 · {{ preview.columns.length }} 列 · 下列展示前
        {{ preview.rows.length }} 行
      </p>
      <div class="table-scroll table-scroll-bounded">
        <table>
          <thead>
            <tr>
              <th v-for="c in preview.columns" :key="c">{{ c }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in preview.rows" :key="i">
              <td v-for="c in preview.columns" :key="c">{{ display(row[c]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="preview" class="panel">
      <h2>3. 列映射</h2>
      <div class="form">
        <label>
          <span>表格布局</span>
          <select v-model="mapping.layout">
            <option value="wide">宽表（一行多指标）</option>
            <option value="long">长表（一行一指标）</option>
          </select>
        </label>
        <label>
          <span>时间列 *</span>
          <select v-model="mapping.time_column">
            <option v-for="c in columns" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <label>
          <span>数据粒度</span>
          <select v-model="mapping.granularity">
            <option value="hour">小时</option>
            <option value="day">天</option>
            <option value="week">周</option>
            <option value="month">月</option>
          </select>
        </label>
        <label>
          <span>归属数据源</span>
          <select v-model="mapping.source_code">
            <option value="">不指定</option>
            <option v-for="s in sources" :key="s.code" :value="s.code">
              {{ s.name }}（{{ s.code }}）
            </option>
          </select>
        </label>
        <label class="check">
          <input v-model="mapping.auto_create_metric" type="checkbox" />
          <span>指标不存在时自动创建</span>
        </label>
      </div>

      <template v-if="mapping.layout === 'wide'">
        <h3>指标列映射</h3>
        <div class="pairs">
          <div v-for="(pair, i) in mapping.pairs" :key="i" class="pair">
            <select v-model="pair.column">
              <option v-for="c in columns" :key="c" :value="c">{{ c }}</option>
            </select>
            <span class="arrow">→</span>
            <input v-model="pair.code" list="metric-options" placeholder="指标编码" />
            <button class="danger" @click="removePair(i)">移除</button>
          </div>
          <datalist id="metric-options">
            <option v-for="m in knownMetrics" :key="m.code" :value="m.code">{{ m.name }}</option>
          </datalist>
          <button @click="addPair">+ 添加映射</button>
        </div>
      </template>

      <template v-else>
        <div class="form">
          <label>
            <span>指标编码列 *</span>
            <select v-model="mapping.metric_column">
              <option value="">请选择</option>
              <option v-for="c in columns" :key="c" :value="c">{{ c }}</option>
            </select>
          </label>
          <label>
            <span>指标值列 *</span>
            <select v-model="mapping.value_column">
              <option value="">请选择</option>
              <option v-for="c in columns" :key="c" :value="c">{{ c }}</option>
            </select>
          </label>
        </div>
        <h3>维度列（可选，将写入指标值的维度标签）</h3>
        <div class="dims">
          <label v-for="c in columns" :key="c" class="check">
            <input v-model="mapping.dim_columns" type="checkbox" :value="c" />
            <span class="mono">{{ c }}</span>
          </label>
        </div>
      </template>

      <div class="actions">
        <button class="primary" :disabled="running" @click="submit">
          {{ running ? '导入中…' : '执行导入' }}
        </button>
        <span v-if="previewing" class="hint">正在解析文件…</span>
      </div>
    </section>

    <section v-if="result" class="panel">
      <h2>4. 导入结果</h2>
      <div class="result" :class="result.status">
        <div class="stat">
          <span class="label">状态</span>
          <strong>{{ result.status }}</strong>
        </div>
        <div class="stat">
          <span class="label">总行数</span>
          <strong>{{ result.total_rows }}</strong>
        </div>
        <div class="stat">
          <span class="label">成功行</span>
          <strong>{{ result.success_rows }}</strong>
        </div>
        <div class="stat">
          <span class="label">失败行</span>
          <strong>{{ result.failed_rows }}</strong>
        </div>
        <div class="stat">
          <span class="label">跳过行</span>
          <strong>{{ result.skipped_rows }}</strong>
        </div>
        <div class="stat">
          <span class="label">写入指标值</span>
          <strong>{{ result.value_count }}</strong>
        </div>
        <div class="stat">
          <span class="label">耗时</span>
          <strong>{{ result.elapsed_ms }} ms</strong>
        </div>
      </div>
      <p v-if="result.metric_codes?.length" class="meta">
        涉及指标：<span class="mono">{{ result.metric_codes.join(', ') }}</span>
      </p>
      <p v-if="result.error_msg" class="error">{{ result.error_msg }}</p>
      <ul v-if="result.error_detail?.length" class="errors">
        <li v-for="(e, i) in result.error_detail.slice(0, 10)" :key="i">
          第 {{ e.row }} 行：{{ e.message }}
        </li>
      </ul>
      <p class="hint">导入完成后可前往「运营总览」查看指标卡与趋势变化。</p>
    </section>

    <section class="panel">
      <h2>导入历史</h2>
      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>文件</th>
            <th>布局</th>
            <th>状态</th>
            <th>行数</th>
            <th>成功 / 失败 / 跳过</th>
            <th>指标值</th>
            <th>耗时</th>
            <th>完成时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in tasks" :key="t.id">
            <td>{{ t.id }}</td>
            <td class="mono">{{ t.file_name }}</td>
            <td>{{ t.layout === 'wide' ? '宽表' : '长表' }}</td>
            <td><span class="tag" :class="t.status">{{ t.status }}</span></td>
            <td>{{ t.total_rows }}</td>
            <td>{{ t.success_rows }} / {{ t.failed_rows }} / {{ t.skipped_rows }}</td>
            <td>{{ t.value_count }}</td>
            <td>{{ t.elapsed_ms ?? '-' }} ms</td>
            <td>{{ t.finished_at ?? '-' }}</td>
          </tr>
          <tr v-if="!tasks.length">
            <td colspan="9" class="empty">暂无导入记录</td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>
  </main>
</template>

<style scoped>
.data-import {
  padding: 32px;
  max-width: 1400px;
  margin: 0 auto;
}
.subtitle {
  color: var(--color-text-secondary);
  margin-bottom: 24px;
  font-size: 14px;
}
.panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 20px;
  margin-bottom: 20px;
  background: var(--color-bg);
}
.panel h2 {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 14px;
}
.panel h3 {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 18px 0 10px;
}
.picker {
  display: flex;
  align-items: center;
  gap: 12px;
}
.upload input {
  display: none;
}
.upload span {
  display: inline-block;
  padding: 8px 16px;
  background: var(--color-primary);
  color: var(--color-bg);
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.file-groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.file-group ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.file-group li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-bg-subtle);
  font-size: 13px;
}
.file-group li.active {
  background: var(--color-primary-light);
}
.file-group li .size {
  color: var(--color-text-muted);
  margin-left: auto;
}
.form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px 16px;
  align-items: end;
}
.form label,
.pairs .pair {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text-secondary);
}
select,
input[type='text'],
input:not([type]) {
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 14px;
}
label.check {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}
.pairs {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pairs .pair {
  flex-direction: row;
  align-items: center;
}
.pairs .pair .arrow {
  color: var(--color-text-muted);
}
.dims {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
}
.actions {
  margin-top: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
}
button {
  padding: 8px 14px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
  cursor: pointer;
  font-size: 13px;
}
button.primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--color-bg);
  font-size: 14px;
  padding: 9px 18px;
}
button.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
button.danger {
  color: var(--color-error);
  border-color: var(--color-error-border);
}
/* 表格滚动容器统一使用全局 .table-scroll，本类仅附加高度限制 */
.table-scroll-bounded {
  max-height: 280px;
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th,
td {
  text-align: left;
  padding: 8px;
  border-bottom: 1px solid var(--color-border-light);
  white-space: nowrap;
}
th {
  color: var(--color-text-secondary);
  font-weight: 500;
  position: sticky;
  top: 0;
  background: var(--color-bg);
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.file-tag {
  margin-left: 10px;
  font-size: 12px;
  color: var(--color-text-secondary);
  background: var(--color-bg-subtle);
  padding: 2px 8px;
  border-radius: 10px;
}
.meta {
  color: var(--color-text-secondary);
  font-size: 13px;
  margin: 6px 0;
}
.result {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
}
.result .stat {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.result .stat .label {
  color: var(--color-text-muted);
  font-size: 12px;
}
.result.success .stat strong {
  color: var(--color-success);
}
.result.partial .stat strong {
  color: var(--color-warning);
}
.result.failed .stat strong {
  color: var(--color-error);
}
.tag {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
}
.tag.success {
  background: var(--color-success-light);
  color: var(--color-success);
}
.tag.partial {
  background: var(--color-warning-light);
  color: var(--color-warning);
}
.tag.failed {
  background: var(--color-error-light);
  color: var(--color-error);
}
.errors {
  color: var(--color-error);
  font-size: 13px;
  padding-left: 18px;
}
.empty,
.hint {
  color: var(--color-text-muted);
  font-size: 13px;
}
.error {
  color: var(--color-error);
  margin: 8px 0;
}

/* ===== P4 统一交互增强 ===== */
.panel {
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.panel:hover {
  border-color: var(--color-primary-border);
}
tbody tr:hover td {
  background: var(--color-bg-hover);
}
button {
  transition: background var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast);
}
button:hover:not(:disabled) {
  border-color: var(--color-primary-border);
}
button.primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.22);
}
.tag {
  font-weight: 600;
}
.metrics .metric,
.engines .engine {
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.metrics .metric:hover,
.engines .engine:hover {
  border-color: var(--color-primary-border);
  box-shadow: var(--shadow-sm);
}

    /* ===== 响应式自适应（窗口缩放） ===== */
    .picker {
      flex-wrap: wrap;
    }
    .actions {
      flex-wrap: wrap;
    }
    @media (max-width: 1024px) {
      .data-import {
        padding: 20px 16px;
      }
    }
    @media (max-width: 768px) {
      .data-import {
        padding: 16px 12px;
      }
      .panel {
        padding: 16px;
      }
      .file-groups {
        grid-template-columns: 1fr;
      }
      .form {
        grid-template-columns: 1fr;
      }
      .pairs .pair {
        flex-wrap: wrap;
      }
      .result {
        grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
      }
    }
    @media (max-width: 480px) {
      .data-import {
        padding: 12px 10px;
      }
      .result {
        grid-template-columns: 1fr 1fr;
      }
      .table-scroll-bounded {
        max-height: 220px;
      }
    }
</style>
