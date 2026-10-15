/**
 * ECharts 定制主题基建（迭代2）
 * - 按需引入（tree-shake）：仅 Line/Bar/Pie + 常用组件 + Canvas 渲染
 * - 注册明暗两套 opscompass 主题，颜色对齐 main.css 令牌
 * - 图表实例统一从本模块创建，避免各页面散装引入全量 echarts
 */
import * as echarts from 'echarts/core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  MarkLineComponent,
  MarkPointComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts, EChartsCoreOption } from 'echarts/core'

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  MarkLineComponent,
  MarkPointComponent,
  DataZoomComponent,
  CanvasRenderer,
])

const LIGHT = {
  color: ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2'],
  backgroundColor: 'transparent',
  textStyle: { fontFamily: "'MiSans', 'PingFang SC', 'Microsoft YaHei', sans-serif", color: '#4b5563' },
  title: { textStyle: { color: '#1f2937', fontSize: 15, fontWeight: 600 } },
  legend: { textStyle: { color: '#4b5563' } },
  tooltip: {
    backgroundColor: '#ffffff',
    borderColor: '#e5e7eb',
    textStyle: { color: '#1f2937', fontSize: 12 },
    extraCssText: 'box-shadow: 0 6px 16px rgba(0,0,0,0.08); border-radius: 8px;',
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: '#d1d5db' } },
    axisLabel: { color: '#6b7280' },
    splitLine: { show: false },
  },
  valueAxis: {
    axisLine: { show: false },
    axisLabel: { color: '#6b7280' },
    splitLine: { lineStyle: { color: '#f1f5f9' } },
  },
}

const DARK = {
  color: ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a78bfa', '#22d3ee'],
  backgroundColor: 'transparent',
  textStyle: { fontFamily: "'MiSans', 'PingFang SC', 'Microsoft YaHei', sans-serif", color: '#c3c7d0' },
  title: { textStyle: { color: '#e5e7eb', fontSize: 15, fontWeight: 600 } },
  legend: { textStyle: { color: '#c3c7d0' } },
  tooltip: {
    backgroundColor: '#232329',
    borderColor: '#2e2e38',
    textStyle: { color: '#e5e7eb', fontSize: 12 },
    extraCssText: 'box-shadow: 0 6px 16px rgba(0,0,0,0.4); border-radius: 8px;',
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: '#3f3f49' } },
    axisLabel: { color: '#a6abb5' },
    splitLine: { show: false },
  },
  valueAxis: {
    axisLine: { show: false },
    axisLabel: { color: '#a6abb5' },
    splitLine: { lineStyle: { color: '#2c2c34' } },
  },
}

echarts.registerTheme('opscompass-light', LIGHT)
echarts.registerTheme('opscompass-dark', DARK)

export type { EChartsCoreOption }
export { echarts }

/** 按当前主题创建图表实例；theme 变化时由调用方重新 init（或调用 setOption 主题差异场景） */
export function initChart(el: HTMLElement, theme: 'light' | 'dark' = 'light'): ECharts {
  return echarts.init(el, theme === 'dark' ? 'opscompass-dark' : 'opscompass-light')
}
