<script setup lang="ts">
/**
 * 换肤按钮：light / dark / system 三态循环切换
 */
import { ref } from 'vue'
import { loadThemeMode, setThemeMode, type ThemeMode } from '@/core/theme'

const mode = ref<ThemeMode>(loadThemeMode())

const ICONS: Record<ThemeMode, string> = {
  light: 'M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6l1.4 1.4m9.9 9.9 1.4 1.4M18.4 5.6l-1.4 1.4m-9.9 9.9-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z',
  dark: 'M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z',
  system: 'M2 7h20v10H2zM9 18h6',
}

const LABELS: Record<ThemeMode, string> = {
  light: '浅色',
  dark: '深色',
  system: '跟随系统',
}

function cycle(): void {
  const order: ThemeMode[] = ['system', 'light', 'dark']
  const next = order[(order.indexOf(mode.value) + 1) % order.length]
  mode.value = next
  setThemeMode(next)
}
</script>

<template>
  <button type="button" class="theme-toggle" :title="`主题：${LABELS[mode]}`" @click="cycle">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path :d="ICONS[mode]" />
    </svg>
    <span>{{ LABELS[mode] }}</span>
  </button>
</template>

<style scoped>
.theme-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  background: var(--bg-surface);
  color: var(--color-text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast);
}
.theme-toggle:hover {
  border-color: var(--color-primary-border);
  color: var(--color-primary);
}
.theme-toggle svg {
  width: 16px;
  height: 16px;
}
</style>
