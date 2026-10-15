<script setup lang="ts">
/**
 * 侧栏图标集：线性 SVG 图标，随主题令牌着色
 * 名称与 App.vue 侧栏菜单一一对应
 */
const ICONS: Record<string, string> = {
  dashboard: 'M4 13h6V4H4zm10 7h6v-9h-6zm-10 0h6v-4H4zm10-10h6V4h-6z',
  compass: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm3.5-12.5L13 13l-4.5 2.5L11 11z',
  metrics: 'M4 20h16M6 16v-5m4 5V7m4 9v-8m4 8v-3',
  ops: 'M12 3 2 8l10 5 10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
  import: 'M12 3v10m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2',
  sources: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3Zm0 0v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6',
  marketing: 'M3 10v4a1 1 0 0 0 1 1h2l4 4V5L6 9H4a1 1 0 0 0-1 1Zm13 0a4 4 0 0 0-2-3.5M16 14a4 4 0 0 0 2-3.5M18 3l1.5 9',
  collect: 'M8 2v4m8-4v4M4 10h16M6 4h12a2 2 0 0 1 2 2v14H4V6a2 2 0 0 1 2-2Zm4 8h.01M16 12h.01M10 16h.01M16 16h.01',
  storage: 'M5 6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2zm2 6h10M8 6h.01M12 6h.01M16 6h.01',
  model: 'M9 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm-3 6H4m16 0h-2M4 12h16m-8-9v18',
  plugins: 'M12 3a3 3 0 0 1 3 3h2a2 2 0 0 1 2 2v2a3 3 0 0 1 0 6v2a2 2 0 0 1-2 2h-2a3 3 0 0 1-6 0H7a2 2 0 0 1-2-2v-2a3 3 0 0 1 0-6V8a2 2 0 0 1 2-2h2a3 3 0 0 1 3-3Z',
  securityLog: 'M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6zm-2 8 2 2 4-4',
  aiGov: 'M12 2c4 2 6 5 6 9s-2 7-6 9c-4-2-6-5-6-9s2-7 6-9Zm0 5v7m0 0 2.5-3.5M12 14 9.5 10.5',
  learning: 'M4 5c3-1.5 6.5-1.5 9 0v14c-2.5-1.5-6-1.5-9 0zm9 0c2.5-1.5 6-1.5 9 0v14c-3-1.5-6.5-1.5-9 0',
  sentiment: 'M12 21c4.5-3.2 7-6.2 7-9.5A4.8 4.8 0 0 0 14.2 7c-1.2 0-2.2.5-2.2.5S11.2 7 10 7A4.8 4.8 0 0 0 5 11.5c0 3.3 2.5 6.3 7 9.5Zm-6-9a5 5 0 0 0 10 0',
  audit: 'M7 4h10a2 2 0 0 1 2 2v14l-2.5-1.5L14 20l-2.5-1.5L9 20l-2.5-1.5L5 20V6a2 2 0 0 1 2-2Zm2 6h6m-6 4h6',
  insight: 'M9 18h6m-6 3h6M12 3a6 6 0 0 1 3.6 10.8c-.8.6-1.1 1-1.1 2.2h-5c0-1.2-.3-1.6-1.1-2.2A6 6 0 0 1 12 3Z',
  knowledge: 'M4 5h4a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H4zm16 0h-4a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h5z',
  siteStudio: 'M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zm4 3h8m-8 4h5',
  siteManager: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  securityCenter: 'M12 3 5 6v5c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6zm-2 9 2 2 4-4',
  apiBridge: 'M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7',
}

withDefaults(defineProps<{ name: string }>(), {})
</script>

<template>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path :d="ICONS[name] ?? ICONS.dashboard" />
  </svg>
</template>
