<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchOverview, fetchTrend, type OverviewItem, type TrendPoint } from '@/api/metrics'

const loading = ref(false)
const error = ref('')
const updatedAt = ref<string | null>(null)
const items = ref<OverviewItem[]>([])
const trends = ref<Record<string, TrendPoint[]>>({})
const activeCode = ref('')

const activeItem = computed(() => items.value.find((i) => i.code === activeCode.value) ?? null)
const activeTrend = computed(() => trends.value[activeCode.value] ?? [])

function formatValue(item: OverviewItem): string {
  if (!item.has_data) return '-'
  return item.value.toLocaleString('zh-CN', {
    minimumFractionDigits: item.precision,
    maximumFractionDigits: item.precision,
  })
}

function formatDelta(item: OverviewItem): string {
  if (item.delta_ratio === null || item.delta_ratio === undefined) return '-'
  const pct = (item.delta_ratio * 100).toFixed(2)
  return `${item.delta_ratio >= 0 ? '+' : ''}${pct}%`
}

/** 将数据点映射为 SVG polyline 的 points 串 */
function sparkline(points: TrendPoint[], width = 100, height = 32): string {
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

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchOverview({ granularity: 'day' })
    items.value = res.data.items ?? []
    updatedAt.value = res.data.stat_date ?? null
    if (items.value.length && !activeCode.value) {
      activeCode.value = items.value[0].code
    }
    const pairs = await Promise.all(
      items.value.map(async (item) => {
        try {
          const t = await fetchTrend(item.code, { granularity: 'day' })
          return [item.code, t.data.points ?? []] as const
        } catch {
          return [item.code, []] as const
        }
      }),
    )
    trends.value = Object.fromEntries(pairs)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <main class="dashboard">
    <header class="head">
      <div>
        <h1>运营智脑</h1>
        <p class="subtitle">
          运营数据总览
          <template v-if="updatedAt"> · 数据日期 {{ updatedAt.slice(0, 10) }}</template>
        </p>
      </div>
      <nav class="nav">
        <router-link to="/">运营总览</router-link>
        <router-link to="/metrics">指标中心</router-link>
      </nav>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section class="cards">
      <button
        v-for="item in items"
        :key="item.code"
        class="card"
        :class="{ active: item.code === activeCode }"
        @click="activeCode = item.code"
      >
        <span class="label">
          {{ item.name }}<em v-if="item.unit">（{{ item.unit }}）</em>
        </span>
        <strong>{{ formatValue(item) }}</strong>
        <span
          class="delta"
          :class="{ up: (item.delta_ratio ?? 0) >= 0, down: (item.delta_ratio ?? 0) < 0 }"
        >
          环比 {{ formatDelta(item) }}
        </span>
        <svg class="spark" viewBox="0 0 100 32" preserveAspectRatio="none">
          <polyline
            :points="sparkline(trends[item.code] ?? [])"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
          />
        </svg>
      </button>
      <p v-if="!items.length && !loading" class="empty">
        暂无上线指标，请到「指标中心」创建并上线
      </p>
    </section>

    <section v-if="activeItem" class="trend">
      <h2>{{ activeItem.name }} · 趋势</h2>
      <svg viewBox="0 0 600 160" preserveAspectRatio="none" class="chart">
        <polyline
          :points="sparkline(activeTrend, 600, 160)"
          fill="none"
          stroke="#2f6fed"
          stroke-width="2"
        />
      </svg>
      <p class="tip">共 {{ activeTrend.length }} 个数据点</p>
    </section>

    <p v-if="loading" class="tip">加载中…</p>
  </main>
</template>

<style scoped>
.dashboard {
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
.nav {
  display: flex;
  gap: 16px;
  font-size: 14px;
}
.nav a {
  color: var(--color-primary);
  text-decoration: none;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
  text-align: left;
  cursor: pointer;
  font: inherit;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.card:hover {
  box-shadow: var(--shadow-card);
  border-color: var(--color-primary-border);
}
.card.active {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
.label {
  color: var(--color-text-muted);
  font-size: 12px;
}
.label em {
  font-style: normal;
  color: var(--color-text-secondary);
  font-size: 11px;
}
.card strong {
  font-size: 26px;
  font-weight: 700;
  color: var(--color-text);
}
.delta {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.delta.up {
  color: var(--color-success);
}
.delta.down {
  color: var(--color-error);
}
.spark {
  width: 100%;
  height: 32px;
}
.trend {
  margin-top: 24px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 20px;
  background: var(--color-bg);
}
.trend h2 {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 12px;
}
.chart {
  width: 100%;
  height: 160px;
}
.empty,
.tip {
  color: var(--color-text-muted);
  margin-top: 12px;
  font-size: 13px;
}
.error {
  color: var(--color-error);
  margin-bottom: 12px;
  font-size: 13px;
}

    /* ===== 响应式自适应（窗口缩放） ===== */
    @media (max-width: 1024px) {
      .dashboard {
        padding: 20px 16px;
      }
    }
    @media (max-width: 768px) {
      .dashboard {
        padding: 16px;
      }
      .cards {
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
      }
      .card {
        padding: 14px;
      }
      .card strong {
        font-size: 22px;
      }
    }
    /* 原重复的 480 媒体块已合并至此：卡片单列 + 内边距收敛 */
    @media (max-width: 480px) {
      .dashboard {
        padding: 14px 10px;
      }
      .cards {
        grid-template-columns: 1fr;
      }
    }
</style>
