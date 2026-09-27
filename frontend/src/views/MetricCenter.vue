<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createMetric,
  deleteMetric,
  fetchMetrics,
  updateMetric,
  type MetricItem,
} from '@/api/metrics'

const loading = ref(false)
const error = ref('')
const rows = ref<MetricItem[]>([])
const total = ref(0)
const keyword = ref('')
const statusFilter = ref('')

const creating = ref(false)
const form = reactive({
  code: '',
  name: '',
  description: '',
  metric_type: 'atomic',
  agg_func: 'sum',
  unit: '',
  precision: 2,
  granularity: 'day',
  status: 'online',
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchMetrics({
      keyword: keyword.value || undefined,
      status: statusFilter.value || undefined,
      page: 1,
      page_size: 100,
    })
    rows.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '加载失败'
  } finally {
    loading.value = false
  }
}

async function submit() {
  error.value = ''
  if (!form.code.trim() || !form.name.trim()) {
    error.value = '指标编码与指标名称必填'
    return
  }
  creating.value = true
  try {
    await createMetric({ ...form, precision: Number(form.precision) })
    Object.assign(form, {
      code: '',
      name: '',
      description: '',
      unit: '',
    })
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '创建失败（编码可能已存在）'
  } finally {
    creating.value = false
  }
}

async function toggleStatus(row: MetricItem) {
  await updateMetric(row.code, { status: row.status === 'online' ? 'offline' : 'online' })
  await load()
}

async function remove(row: MetricItem) {
  if (!window.confirm(`确认删除指标「${row.name}（${row.code}）」？其指标值将一并删除。`)) return
  await deleteMetric(row.code)
  await load()
}

onMounted(load)
</script>

<template>
  <main class="metric-center">
    <header class="head">
      <h1>指标中心</h1>
      <p class="subtitle">统一管理指标口径、单位、聚合方式与上下线状态</p>
    </header>

    <section class="panel">
      <h2>新建指标</h2>
      <div class="form">
        <label>
          <span>指标编码 *</span>
          <input v-model="form.code" placeholder="如 pay_amount" />
        </label>
        <label>
          <span>指标名称 *</span>
          <input v-model="form.name" placeholder="如 支付金额" />
        </label>
        <label>
          <span>单位</span>
          <input v-model="form.unit" placeholder="元 / 单 / %" />
        </label>
        <label>
          <span>类型</span>
          <select v-model="form.metric_type">
            <option value="atomic">原子指标</option>
            <option value="derived">派生指标</option>
          </select>
        </label>
        <label>
          <span>聚合方式</span>
          <select v-model="form.agg_func">
            <option value="sum">sum</option>
            <option value="avg">avg</option>
            <option value="count">count</option>
            <option value="count_distinct">count_distinct</option>
            <option value="max">max</option>
            <option value="min">min</option>
            <option value="ratio">ratio</option>
          </select>
        </label>
        <label>
          <span>粒度</span>
          <select v-model="form.granularity">
            <option value="hour">小时</option>
            <option value="day">天</option>
            <option value="week">周</option>
            <option value="month">月</option>
          </select>
        </label>
        <label>
          <span>小数位</span>
          <input v-model.number="form.precision" type="number" min="0" max="6" />
        </label>
        <label class="wide">
          <span>口径说明</span>
          <input v-model="form.description" placeholder="计算口径 / 业务含义" />
        </label>
        <button class="primary" :disabled="creating" @click="submit">
          {{ creating ? '提交中…' : '创建指标' }}
        </button>
      </div>
    </section>

    <section class="panel">
      <div class="toolbar">
        <h2>指标列表（{{ total }}）</h2>
        <div class="filters">
          <input v-model="keyword" placeholder="搜索编码 / 名称" @keyup.enter="load" />
          <select v-model="statusFilter" @change="load">
            <option value="">全部状态</option>
            <option value="online">已上线</option>
            <option value="draft">草稿</option>
            <option value="offline">已下线</option>
          </select>
          <button @click="load">查询</button>
        </div>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>编码</th>
            <th>名称</th>
            <th>类型</th>
            <th>聚合</th>
            <th>单位</th>
            <th>粒度</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td class="mono">{{ row.code }}</td>
            <td>{{ row.name }}</td>
            <td>{{ row.metric_type === 'atomic' ? '原子' : '派生' }}</td>
            <td class="mono">{{ row.agg_func }}</td>
            <td>{{ row.unit || '-' }}</td>
            <td>{{ row.granularity }}</td>
            <td>
              <span class="tag" :class="row.status">{{ row.status }}</span>
            </td>
            <td class="ops">
              <button @click="toggleStatus(row)">
                {{ row.status === 'online' ? '下线' : '上线' }}
              </button>
              <button class="danger" @click="remove(row)">删除</button>
            </td>
          </tr>
          <tr v-if="!rows.length && !loading">
            <td colspan="8" class="empty">暂无指标，请先在上方创建</td>
          </tr>
        </tbody>
      </table>
      </div>
      <p v-if="loading" class="tip">加载中…</p>
    </section>
  </main>
</template>

<style scoped>
.metric-center {
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
  margin: 0 0 16px;
}
.form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px 16px;
  align-items: end;
}
.form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.form label.wide {
  grid-column: 1 / -1;
}
.form input,
.form select,
.filters input,
.filters select {
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 14px;
}
button {
  padding: 8px 14px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
  cursor: pointer;
  font-size: 14px;
}
button.primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--color-bg);
}
button.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
button.danger {
  color: var(--color-error);
  border-color: var(--color-error-border);
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.filters {
  display: flex;
  gap: 8px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
th,
td {
  text-align: left;
  padding: 10px 8px;
  border-bottom: 1px solid var(--color-border-light);
}
th {
  color: var(--color-text-secondary);
  font-weight: 500;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.tag {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
}
.tag.online {
  background: var(--color-success-light);
  color: var(--color-success);
}
.tag.offline {
  background: var(--color-error-light);
  color: var(--color-error);
}
.ops {
  display: flex;
  gap: 8px;
}
.empty,
.tip {
  color: var(--color-text-muted);
  text-align: center;
  padding: 16px;
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
    .toolbar {
      flex-wrap: wrap;
    }
    .filters {
      flex-wrap: wrap;
    }
    @media (max-width: 1024px) {
      .metric-center {
        padding: 20px 16px;
      }
    }
    @media (max-width: 768px) {
      .metric-center {
        padding: 16px 12px;
      }
      .panel {
        padding: 16px;
      }
      .form {
        grid-template-columns: 1fr;
      }
      .filters select {
        width: 100%;
      }
    }
    @media (max-width: 480px) {
      .metric-center {
        padding: 12px 10px;
      }
    }
</style>
