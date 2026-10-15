<script setup lang="ts">
/**
 * 骨架屏：text / title / card / chart 四种形态，行数可配
 * 统一 shimmer 动效，尊重 reduced-motion
 */
withDefaults(
  defineProps<{
    type?: 'text' | 'title' | 'card' | 'chart'
    rows?: number
  }>(),
  { type: 'text', rows: 3 },
)
</script>

<template>
  <div v-if="type === 'card'" class="sk-card" :style="{ '--sk-rows': rows }" aria-hidden="true">
    <div v-for="i in rows" :key="i" class="sk-line" :class="{ short: i === rows }" />
  </div>
  <div v-else-if="type === 'chart'" class="sk-chart" aria-hidden="true" />
  <div v-else class="sk-block" aria-hidden="true">
    <div v-for="i in rows" :key="i" class="sk-line" :class="type === 'title' && i === 1 ? 'title' : i === rows ? 'short' : ''" />
  </div>
</template>

<style scoped>
.sk-line,
.sk-chart {
  background: linear-gradient(90deg, var(--color-border-light) 25%, var(--color-border) 50%, var(--color-border-light) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
  border-radius: var(--radius-sm);
}
.sk-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}
.sk-line {
  height: 12px;
  width: 100%;
}
.sk-line.short {
  width: 62%;
}
.sk-line.title {
  height: 18px;
  width: 46%;
}
.sk-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
}
.sk-chart {
  height: 160px;
  width: 100%;
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
  .sk-line,
  .sk-chart {
    animation: none;
  }
}
</style>
