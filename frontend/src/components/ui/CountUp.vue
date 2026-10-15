<script setup lang="ts">
/**
 * 数字滚动（count-up）微动效：值变化时从旧值缓动到新值
 * - easeOutCubic 缓动 + rAF；prefers-reduced-motion 时直出
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useReducedMotion } from '@/composables/useReducedMotion'

const props = withDefaults(
  defineProps<{
    /** 目标数值；null/undefined 时显示 placeholder */
    value?: number | null
    /** 小数位 */
    precision?: number
    /** 动画时长 ms */
    duration?: number
    /** 空值占位符 */
    placeholder?: string
  }>(),
  { value: null, precision: 0, duration: 600, placeholder: '-' },
)

const { reduced } = useReducedMotion()
const display = ref(props.value ?? 0)
const raf = ref<number>()

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

function animateTo(target: number): void {
  if (raf.value) cancelAnimationFrame(raf.value)
  if (reduced.value || props.duration <= 0) {
    display.value = target
    return
  }
  const from = display.value
  const start = performance.now()
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / props.duration)
    display.value = from + (target - from) * easeOutCubic(t)
    if (t < 1) raf.value = requestAnimationFrame(step)
  }
  raf.value = requestAnimationFrame(step)
}

watch(
  () => props.value,
  (v) => animateTo(v ?? 0),
)

onMounted(() => animateTo(props.value ?? 0))

const text = computed(() => {
  if (props.value === null || props.value === undefined) return props.placeholder
  return display.value.toLocaleString('zh-CN', {
    minimumFractionDigits: props.precision,
    maximumFractionDigits: props.precision,
  })
})
</script>

<template>
  <span class="count-up" :title="props.value !== null && props.value !== undefined ? String(props.value) : undefined">{{
    text
  }}</span>
</template>

<style scoped>
.count-up {
  font-family: var(--font-numeric);
  font-variant-numeric: tabular-nums;
}
</style>
