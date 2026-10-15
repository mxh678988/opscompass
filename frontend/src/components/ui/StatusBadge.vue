<script setup lang="ts">
/**
 * 状态徽标：语义色由令牌承载，内置 ok / warn / bad / muted / info 五态
 */
withDefaults(
  defineProps<{
    status?: 'ok' | 'warn' | 'bad' | 'muted' | 'info'
    /** 是否显示小圆点 */
    dot?: boolean
  }>(),
  { status: 'muted', dot: false },
)
</script>

<template>
  <span class="badge" :class="`is-${status}`">
    <i v-if="dot" class="dot" aria-hidden="true" />
    <slot />
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  line-height: 1.6;
  white-space: nowrap;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: currentColor;
  opacity: 0.85;
}
.is-ok {
  color: var(--color-success);
  background: var(--color-success-light);
  border: 1px solid var(--color-success-border);
}
.is-warn {
  color: var(--color-warning);
  background: var(--color-warning-light);
  border: 1px solid var(--color-warning-border);
}
.is-bad {
  color: var(--color-error);
  background: var(--color-error-light);
  border: 1px solid var(--color-error-border);
}
.is-muted {
  color: var(--color-text-secondary);
  background: var(--bg-subtle);
  border: 1px solid var(--color-border-light);
}
.is-info {
  color: var(--color-primary);
  background: var(--color-primary-light);
  border: 1px solid var(--color-primary-border);
}
</style>
