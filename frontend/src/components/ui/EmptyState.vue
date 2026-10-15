<script setup lang="ts">
/**
 * 空状态：统一文案 + 可选操作按钮（router-link 或原生事件）
 */
defineProps<{
  title?: string
  description?: string
  actionText?: string
  actionTo?: string
}>()
</script>

<template>
  <div class="empty-state">
    <div class="icon" aria-hidden="true">
      <svg viewBox="0 0 48 48" fill="none">
        <circle cx="24" cy="24" r="18" stroke="currentColor" stroke-width="2" opacity="0.4" />
        <path
          d="M24 16v10m0 4v.01"
          stroke="currentColor"
          stroke-width="2.4"
          stroke-linecap="round"
          opacity="0.7"
        />
      </svg>
    </div>
    <p class="title">{{ title || '暂无数据' }}</p>
    <p v-if="description" class="desc">{{ description }}</p>
    <router-link v-if="actionText && actionTo" :to="actionTo" class="action">{{ actionText }}</router-link>
    <button v-else-if="actionText" type="button" class="action">
      <slot name="action" />
      {{ actionText }}
    </button>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px 24px;
  text-align: center;
  color: var(--color-text-muted);
}
.icon {
  width: 48px;
  height: 48px;
  color: var(--color-text-muted);
  margin-bottom: 4px;
}
.title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin: 0;
}
.desc {
  font-size: 13px;
  margin: 0;
  max-width: 420px;
}
.action {
  margin-top: 12px;
  padding: 6px 16px;
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-md);
  color: var(--color-primary);
  background: var(--color-primary-light);
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}
.action:hover {
  border-color: var(--color-primary);
  background: var(--bg-active);
}
</style>
