<script setup lang="ts">
/**
 * 数据卡片：标题 + 数值（CountUp 滚动）+ 环比 + 迷你趋势
 * 纯展示组件，数据传入即可；点击事件由父组件绑定
 */
import { computed } from 'vue'
import CountUp from './CountUp.vue'

const props = withDefaults(
  defineProps<{
    label: string
    unit?: string
    value?: number | null
    precision?: number
    /** 环比比率（小数），null 不展示 */
    deltaRatio?: number | null
    /** 迷你趋势点列（可选） */
    spark?: number[]
    active?: boolean
    loading?: boolean
  }>(),
  { unit: '', value: null, precision: 0, deltaRatio: null, spark: () => [], active: false, loading: false },
)

const deltaText = computed(() => {
  if (props.deltaRatio === null || props.deltaRatio === undefined) return '-'
  const pct = (props.deltaRatio * 100).toFixed(2)
  return `${props.deltaRatio >= 0 ? '+' : ''}${pct}%`
})

const deltaTone = computed<'up' | 'down' | 'flat'>(() => {
  if (props.deltaRatio === null || props.deltaRatio === undefined) return 'flat'
  return props.deltaRatio >= 0 ? 'up' : 'down'
})

/** 迷你趋势折线（纯 SVG，避免为 sparkline 引入图表库） */
function sparkPoints(points: number[], width = 100, height = 30): string {
  if (points.length < 2) return ''
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  return points
    .map((v, i) => {
      const x = (i / (points.length - 1)) * width
      const y = height - 3 - ((v - min) / span) * (height - 6)
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')
}
</script>

<template>
  <div class="data-card" :class="{ active, 'is-loading': loading }" :aria-busy="loading">
    <template v-if="loading">
      <span class="line label" />
      <span class="line value" />
      <span class="line delta" />
    </template>
    <template v-else>
      <span class="label">
        {{ label }}<em v-if="unit">（{{ unit }}）</em>
      </span>
      <strong class="value"><CountUp :value="value" :precision="precision" /></strong>
      <span class="delta" :class="deltaTone">
        环比 {{ deltaText }}
      </span>
      <svg v-if="spark.length >= 2" class="spark" viewBox="0 0 100 30" preserveAspectRatio="none">
        <polyline :points="sparkPoints(spark)" fill="none" stroke="currentColor" stroke-width="1.5" />
      </svg>
    </template>
  </div>
</template>

<style scoped>
.data-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast);
}
.data-card:hover {
  box-shadow: var(--shadow-card);
  border-color: var(--color-primary-border);
  transform: translateY(-1px);
}
.data-card.active {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-light);
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
.value {
  font-family: var(--font-numeric);
  font-size: 26px;
  font-weight: 700;
  color: var(--color-text);
  line-height: 1.2;
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
  height: 30px;
  color: var(--color-primary);
}
/* 骨架形态 */
.is-loading .line {
  display: block;
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, var(--color-border-light) 25%, var(--color-border) 50%, var(--color-border-light) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}
.is-loading .label {
  width: 40%;
  height: 12px;
}
.is-loading .value {
  width: 55%;
  height: 24px;
}
.is-loading .delta {
  width: 30%;
  height: 12px;
}
@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .data-card:hover {
    transform: none;
  }
  .is-loading .line {
    animation: none;
  }
}
</style>
