<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { fetchCompass, type BreakdownItem, type CompassMetric, type CompassOut } from '@/api/compass'

const loading = ref(false)
const error = ref('')
const granularity = ref('day')
const dimKey = ref('')
const data = ref<CompassOut | null>(null)

const items = computed<CompassMetric[]>(() => data.value?.items ?? [])
const dimKeys = computed<string[]>(() => data.value?.available_dim_keys ?? [])
const latest = computed(() => data.value?.latest_stat ?? null)
const withData = computed(() => items.value.filter((i) => i.has_data).length)

function fmt(value: number | null | undefined, precision = 2): string {
  if (value === null || value === undefined) return '-'
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  })
}

function formatDelta(delta: number | null | undefined): string {
  if (delta === null || delta === undefined) return '-'
  return `${delta >= 0 ? '+' : ''}${(delta * 100).toFixed(2)}%`
}

function deltaClass(delta: number | null | undefined): string {
  if (delta === null || delta === undefined) return ''
  return delta >= 0 ? 'up' : 'down'
}

/** 迷你趋势折线 */
function sparkline(points: { value: number }[], width = 100, height = 32): string {
  const values = points.map((p) => p.value)
  if (values.length < 2) return ''
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width
      const y = height - 3 - ((v - min) / span) * (height - 6)
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')
}

/** 拆解条形宽度：按该指标各维度取值中的最大值归一化 */
function barWidth(row: BreakdownItem, metric: CompassMetric): string {
  const max = Math.max(...metric.breakdown.map((b) => b.value), 0)
  if (!max) return '0%'
  return `${Math.max((row.value / max) * 100, 2).toFixed(1)}%`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchCompass({
      granularity: granularity.value,
      dim_key: dimKey.value || undefined,
    })
    data.value = res.data
    if (dimKey.value && !res.data.available_dim_keys.includes(dimKey.value)) {
      dimKey.value = ''
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '加载失败'
  } finally {
    loading.value = false
  }
}

watch([granularity, dimKey], load)
onMounted(load)
</script>

<template>
  <main class="compass">
    <header class="head">
      <div>
        <h1>全景罗盘</h1>
        <p class="subtitle">
          上线指标 {{ items.length }} 个（有数据 {{ withData }} 个）· 粒度 {{ granularity }}
          <template v-if="latest"> · 数据日期 {{ latest.slice(0, 10) }}</template>
        </p>
      </div>
      <div class="controls">
        <label>
          粒度
          <select v-model="granularity">
            <option value="day">按日</option>
            <option value="week">按周</option>
            <option value="month">按月</option>
          </select>
        </label>
        <label>
          拆解维度
          <select v-model="dimKey">
            <option value="">不分组</option>
            <option v-for="key in dimKeys" :key="key" :value="key">{{ key }}</option>
          </select>
        </label>
      </div>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section class="grid">
      <article v-for="metric in items" :key="metric.code" class="card">
        <div class="card-head">
          <span class="name">
            {{ metric.name }}<em v-if="metric.unit">（{{ metric.unit }}）</em>
          </span>
          <span class="delta" :class="deltaClass(metric.delta_ratio)">
            环比 {{ formatDelta(metric.delta_ratio) }}
          </span>
        </div>

        <strong class="value">{{ metric.has_data ? fmt(metric.value, metric.precision) : '-' }}</strong>
        <p class="meta">
          上期 {{ fmt(metric.prev_value, metric.precision) }}
          <template v-if="metric.stat_time"> · {{ metric.stat_time.slice(0, 10) }}</template>
        </p>

        <svg class="spark" viewBox="0 0 100 32" preserveAspectRatio="none">
          <polyline :points="sparkline(metric.trend)" fill="none" stroke="currentColor" stroke-width="1.5" />
        </svg>

        <div v-if="dimKey && metric.breakdown.length" class="breakdown">
          <div class="bd-title">
            「{{ data?.dim_name ?? dimKey }}」拆解
            <span class="bd-note">占比按各维度取值合计</span>
          </div>
          <div v-for="row in metric.breakdown" :key="row.dim_value" class="bd-row">
            <span class="bd-name" :title="row.dim_value">{{ row.dim_value }}</span>
            <span class="bd-bar"><i :style="{ width: barWidth(row, metric) }"></i></span>
            <span class="bd-val">{{ fmt(row.value, metric.precision) }}</span>
            <span class="bd-share">{{ row.share === null || row.share === undefined ? '-' : `${(row.share * 100).toFixed(1)}%` }}</span>
            <span class="bd-delta" :class="deltaClass(row.delta_ratio)">{{ formatDelta(row.delta_ratio) }}</span>
          </div>
        </div>
        <p v-else-if="dimKey" class="bd-empty">该指标暂无「{{ dimKey }}」维度数据</p>
      </article>
      <p v-if="!items.length && !loading" class="empty">暂无上线指标，请到「指标中心」创建并上线</p>
    </section>

    <p v-if="loading" class="tip">加载中…</p>
  </main>
</template>

<style scoped>
.compass {
  padding: 32px;
  max-width: 1400px;
  margin: 0 auto;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}
.subtitle {
  color: var(--color-text-secondary);
  font-size: 14px;
}
.controls {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--color-text-secondary);
  align-items: center;
}
.controls select {
  padding: 5px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font: inherit;
  background: var(--color-bg);
  color: var(--color-text);
  cursor: pointer;
}
.controls select:focus {
  border-color: var(--color-focus);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
  outline: none;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 16px;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
  transition: box-shadow var(--transition-fast), border-color var(--transition-fast);
}
.card:hover {
  box-shadow: var(--shadow-card);
  border-color: var(--color-primary-border);
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.name {
  color: var(--color-text-muted);
  font-size: 13px;
}
.name em {
  font-style: normal;
  color: var(--color-text-secondary);
}
.value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
}
.meta {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-muted);
}
.delta {
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: nowrap;
}
.delta.up {
  color: var(--color-success);
}
.delta.down {
  color: var(--color-error);
}
.spark {
  width: 100%;
  height: 36px;
}
.breakdown {
  border-top: 1px dashed var(--color-border-light);
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bd-title {
  font-size: 12px;
  color: var(--color-text-muted);
}
.bd-row {
  display: grid;
  grid-template-columns: 84px 1fr 96px 52px 62px;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.bd-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
}
.bd-bar {
  display: block;
  height: 8px;
  background: var(--color-bg-hover);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.bd-bar i {
  display: block;
  height: 100%;
  background: var(--color-primary);
  border-radius: var(--radius-full);
}
.bd-val {
  text-align: right;
  color: var(--color-text);
}
.bd-share {
  text-align: right;
  color: var(--color-text-muted);
}
.bd-delta {
  text-align: right;
  color: var(--color-text-secondary);
}
.bd-delta.up {
  color: var(--color-success);
}
.bd-delta.down {
  color: var(--color-error);
}
.bd-empty,
.empty,
.tip {
  color: var(--color-text-muted);
  font-size: 13px;
}
.error {
  color: var(--color-error);
  margin-bottom: 12px;
  font-size: 13px;
}

@media (max-width: 768px) {
  .compass {
    padding: 16px;
  }
  .grid {
    grid-template-columns: 1fr;
  }
  .bd-row {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}

    /* ===== 响应式自适应（窗口缩放） ===== */
    @media (max-width: 1000px) {
      .bd-row {
        grid-template-columns: 1fr;
        gap: 2px;
      }
    }
    @media (max-width: 480px) {
      .compass {
        padding: 12px 10px;
      }
    }
</style>
