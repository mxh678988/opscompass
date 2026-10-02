<script setup lang="ts">
// PWA 安装引导条：浏览器判定站点可安装时展示，支持一键安装或忽略
import { usePwaInstall } from '@/composables/usePwaInstall'

const { visible, install, dismiss } = usePwaInstall()
</script>

<template>
  <div v-if="visible" class="install-bar" role="dialog" aria-label="安装运营智脑">
    <div class="install-text">
      <strong>把运营智脑安装到桌面</strong>
      <span>安装后可从桌面或开始菜单直接打开，并支持离线访问已缓存页面。</span>
    </div>
    <div class="install-actions">
      <button class="btn-install" type="button" @click="install">立即安装</button>
      <button class="btn-later" type="button" @click="dismiss">暂不</button>
    </div>
  </div>
</template>

<style scoped>
.install-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 12px 32px 0;
  padding: 12px 16px;
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-md);
  background: var(--color-primary-light);
  box-shadow: var(--shadow-sm);
}
.install-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}
.install-text strong {
  font-size: 13.5px;
  color: var(--color-text);
}
.install-text span {
  font-size: 12.5px;
  color: var(--color-text-secondary);
}
.install-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.btn-install,
.btn-later {
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}
.btn-install {
  border: 1px solid var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}
.btn-install:hover {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}
.btn-later {
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text-secondary);
}
.btn-later:hover {
  border-color: var(--color-text-muted);
  color: var(--color-text);
}

@media (max-width: 768px) {
  .install-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
    margin: 10px 16px 0;
  }
  .install-actions {
    width: 100%;
  }
  .btn-install,
  .btn-later {
    flex: 1;
  }
}
</style>
