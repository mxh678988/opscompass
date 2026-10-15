<script setup lang="ts">
// 运营总览：NBA 行动卡 + 指标数据卡（CountUp）+ ECharts 趋势图
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { fetchOverview, fetchTrend, type OverviewItem, type TrendPoint } from '@/api/metrics'

import DataCard from '@/components/ui/DataCard.vue'
import NbaCard from '@/components/ui/NbaCard.vue'
import Skeleton from '@/components/ui/Skeleton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { initChart, type EChartsCoreOption } from '@/core/echarts'

const loading = ref(false)
const error = ref('')
const updatedAt = ref<string | null>(null)
const items = ref<OverviewItem[]>([])
const trends = ref<Record<string, TrendPoint[]>>({})
const activeCode = ref('')
const initialLoading = ref(true)

const activeItem = computed(() => items.value.find((i) => i.code === activeCode.value) ?? null)
const activeTrend = computed(() => trends.value[activeCode.value] ?? [])

/** 基于现有概览数据生成 Next Best Action（规则版，后续迭代3接入运营参谋） */
const actions = computed(() => {
  const list: Array<{ id: string; title: string; desc?: string; level: 'high' | 'mid' | 'low'; link: string }> = []
  for (const item of items.value) {
    if (item.delta_ratio === null || item.delta_ratio === undefined) continue
    const ratio = item.delta_ratio
    const name = item.name || item.code
    if (ratio < -0.05) {
      list.push({
        id: `high-${item.code}`,
        title: `${name} 环比下降 ${(Math.abs(ratio) * 100).toFixed(1)}%`,
        desc: '建议优先核查数据源连接、采集调度与口径一致性',
        level: 'high',
        link: '/ops',
      })
    } else if (ratio < 0) {
      list.push({
        id: `mid-${item.code}`,
        title: `${name} 较上期小幅回落`,
        desc: '降幅在 5% 以内，建议关注趋势是否延续',
        level: 'mid',
        link: '/metrics',
      })
    } else {
      list.push({
        id: `low-${item.code}`,
        title: `${name} 保持增长态势`,
        desc: '环比上升，当前无需干预',
        level: 'low',
        link: '/metrics',
      })
    }
  }
  // 高优先级优先，至多展示 3 条
  const order = { high: 0, mid: 1, low: 2 }
  return list.sort((a, b) => order[a.level] - order[b.level]).slice(0, 3)
})

async function load() {
  loading.value = true
  initialLoading.value = false
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

/** ECharts 趋势图 */
let chart: ReturnType<typeof initChart> | null = null
const chartEl = ref<HTMLElement | null>(null)
const chartTheme = ref<'light' | 'dark'>('light')

function renderChart(): void {
  if (!chartEl.value || !activeItem.value) return
  if (!chart) {
    chart = initChart(chartEl.value, chartTheme.value)
  }
  const cssVar = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim()
  const chartPrimary = cssVar('--chart-primary') || '#2563eb'
  const chartPrimarySoft = cssVar('--chart-primary-soft') || 'rgba(37,99,235,0.02)'
  const points = activeTrend.value
  const option: EChartsCoreOption = {
    animationDuration: 500,
    grid: { left: 12, right: 16, top: 28, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: points.map((p) => String(p.stat_time).slice(0, 10)),
    },
    yAxis: { type: 'value', scale: true },
    series: [
      {
        name: activeItem.value.name,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        showSymbol: false,
        data: points.map((p) => p.value),
        lineStyle: { width: 2 },
        areaStyle: {
          opacity: 0.14,
          color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: chartPrimary }, { offset: 1, color: chartPrimarySoft }] },
        },
      },
    ],
  }
  chart.setOption(option, true)
}

/** 主题变化时重建图表 */
function syncChartTheme(): void {
  const resolved = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
  if (resolved !== chartTheme.value) {
    chartTheme.value = resolved
    chart?.dispose()
    chart = null
    nextTick(renderChart)
  }
}

watch([activeItem, activeTrend], () => nextTick(renderChart), { deep: true })

onMounted(async () => {
  await load()
  syncChartTheme()
  const observer = new MutationObserver(syncChartTheme)
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  window.addEventListener('resize', resizeChart)
  syncChartTheme()
  return
})

function resizeChart(): void {
  chart?.resize()
}

onBeforeUnmount(() => {
  chart?.dispose()
  chart = null
  window.removeEventListener('resize', resizeChart)
})
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
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <NbaCard :actions="actions" />

    <section class="cards">
      <!-- 骨架屏 -->
      <template v-if="initialLoading || loading">
        <Skeleton v-for="i in 3" :key="i" type="card" :rows="3" />
      </template>
      <!-- 数据 -->
      <template v-else>
        <button
          v-for="item in items"
          :key="item.code"
          class="card-btn"
          type="button"
          @click="activeCode = item.code"
        >
          <DataCard
            :label="item.name"
            :unit="item.unit"
            :value="item.has_data ? item.value : null"
            :precision="item.precision"
            :delta-ratio="item.delta_ratio"
            :spark="(trends[item.code] ?? []).map((p) => p.value)"
            :active="item.code === activeCode"
          />
        </button>
      </template>
      <EmptyState
        v-if="!items.length && !initialLoading && !loading"
        title="暂无上线指标"
        description="请到「指标中心」创建并上线指标，运营总览将自动展示"
        action-text="前往指标中心"
        action-to="/metrics"
      />
    </section>

    <section v-if="activeItem" class="trend">
      <div class="trend-head">
        <h2>{{ activeItem.name }} · 趋势</h2>
        <span class="tip">共 {{ activeTrend.length }} 个数据点</span>
      </div>
      <div ref="chartEl" class="chart" />
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
.head h1 {
  margin: 0 0 4px;
  font-size: 22px;
  color: var(--color-text);
}
.subtitle {
  color: var(--color-text-secondary);
  font-size: 14px;
  margin: 0;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.card-btn {
  all: unset;
  display: block;
  cursor: pointer;
  border-radius: var(--radius-lg);
}
.card-btn:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.trend {
  margin-top: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 20px;
  background: var(--bg-surface);
}
.trend-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.trend h2 {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}
.chart {
  width: 100%;
  height: 240px;
}
.empty,
.tip {
  color: var(--color-text-muted);
  margin-top: 12px;
  font-size: 13px;
}
.tip {
  margin: 0;
}
.error {
  color: var(--color-error);
  margin-bottom: 12px;
  font-size: 13px;
}

/* ===== 响应式 ===== */
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
}
@media (max-width: 480px) {
  .dashboard {
    padding: 14px 10px;
  }
  .cards {
    grid-template-columns: 1fr;
  }
  .chart {
    height: 200px;
  }
}
</style>
