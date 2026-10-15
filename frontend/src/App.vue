<script setup lang="ts">
// 应用根组件：顶栏（品牌/换肤/用户区）+ 可折叠侧栏（分组导航）+ 路由出口
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import PwaInstallPrompt from '@/components/PwaInstallPrompt.vue'
import ThemeToggle from '@/components/ui/ThemeToggle.vue'
import SidebarIcon from '@/components/ui/SidebarIcon.vue'
import { useAuthStore } from '@/store/auth'
import { initTheme } from '@/core/theme'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

/** 菜单分组：工作台 / 数据接入 / 智能治理 / 站点与能力 */
const menuGroups = [
  {
    key: 'core',
    label: '工作台',
    items: [
      { to: '/', label: '运营总览', icon: 'dashboard' },
      { to: '/compass', label: '全景罗盘', icon: 'compass' },
      { to: '/metrics', label: '指标中心', icon: 'metrics' },
      { to: '/ops', label: '运营参谋', icon: 'ops' },
    ],
  },
  {
    key: 'data',
    label: '数据接入',
    items: [
      { to: '/data-import', label: '数据导入', icon: 'import' },
      { to: '/data-sources', label: '数据源', icon: 'sources' },
      { to: '/marketing', label: '营销渠道', icon: 'marketing' },
      { to: '/collect', label: '采集调度', icon: 'collect' },
      { to: '/storage', label: '存储适配', icon: 'storage' },
      { to: '/model', label: '模型中心', icon: 'model' },
    ],
  },
  {
    key: 'govern',
    label: '智能治理',
    items: [
      { to: '/plugins', label: '插件市场', icon: 'plugins' },
      { to: '/security-log', label: '安全日志', icon: 'securityLog' },
      { to: '/ai-governance', label: 'AI 治理', icon: 'aiGov' },
      { to: '/learning', label: '学习进化', icon: 'learning' },
      { to: '/sentiment', label: '舆情监控', icon: 'sentiment' },
      { to: '/audit', label: '审计日志', icon: 'audit' },
      { to: '/insight', label: '洞察中心', icon: 'insight' },
      { to: '/knowledge-center', label: '知识中心', icon: 'knowledge' },
    ],
  },
  {
    key: 'site',
    label: '站点与能力',
    items: [
      { to: '/site-studio', label: '响应式网站', icon: 'siteStudio' },
      { to: '/site-manager', label: '资源管理', icon: 'siteManager' },
      { to: '/security-center', label: '安全压缩', icon: 'securityCenter' },
      { to: '/api-bridge', label: 'API 代申请', icon: 'apiBridge' },
    ],
  },
]

/** 登录页不展示导航框架 */
const showChrome = computed(() => route.name !== 'login')

/** 侧栏折叠状态（持久化；窄屏默认折叠） */
const SIDEBAR_KEY = 'opscompass-sidebar'
const collapsed = ref(localStorage.getItem(SIDEBAR_KEY) === '1')

function toggleSidebar(): void {
  collapsed.value = !collapsed.value
  localStorage.setItem(SIDEBAR_KEY, collapsed.value ? '1' : '0')
}

/** 是否命中菜单项（含子路径，如 /metrics 的子路由） */
function isActive(to: string): boolean {
  return route.path === to || route.path.startsWith(to + '/')
}

onMounted(async () => {
  initTheme()
  if (!auth.isLoggedIn) return
  try {
    await auth.loadProfile()
  } catch {
    // 令牌失效由 request 拦截器统一跳转登录页
  }
})

onBeforeUnmount(() => undefined)

async function handleLogout() {
  await auth.logout()
  router.replace({ name: 'login' })
}
</script>

<template>
  <template v-if="showChrome">
    <header class="topbar">
      <button type="button" class="burger" :aria-expanded="!collapsed" aria-label="切换侧栏" @click="toggleSidebar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <path v-if="!collapsed" d="M4 6h16M4 12h16M4 18h16" />
          <path v-else d="M4 6h16M4 12h10M4 18h16" />
        </svg>
      </button>
      <div class="brandbox">
        <img class="logo" src="/favicon.ico" alt="运营智脑" />
        <span class="brandname">运营智脑</span>
        <span class="version">v0.15.0</span>
      </div>
      <div class="spacer" />
      <ThemeToggle />
      <div class="userbox">
        <span class="uname">{{ auth.displayName }}</span>
        <span v-if="auth.isSuperuser" class="role-tag">超级管理员</span>
        <span v-else-if="auth.roles.length" class="role-tag">{{ auth.roles.join(' / ') }}</span>
        <button class="logout" type="button" @click="handleLogout">退出</button>
      </div>
    </header>

    <aside class="sidebar" :class="{ collapsed }" aria-label="主导航">
      <nav class="menu">
        <template v-for="g in menuGroups" :key="g.key">
          <p class="group-label">{{ g.label }}</p>
          <RouterLink
            v-for="l in g.items"
            :key="l.to"
            :to="l.to"
            class="link"
            :class="{ active: isActive(l.to) }"
            :title="collapsed ? l.label : undefined"
          >
            <span class="icon"><SidebarIcon :name="l.icon" /></span>
            <span class="text">{{ l.label }}</span>
          </RouterLink>
        </template>
      </nav>
      <div class="sidebar-foot">
        <span v-if="!collapsed">BY LAOMENG 网络工作室</span>
      </div>
    </aside>

    <PwaInstallPrompt />
    <main class="content" :class="{ collapsed }">
      <RouterView />
    </main>
  </template>
  <RouterView v-else />
  <footer v-if="showChrome" class="footer">
    <p>BY LAOMENG网络工作室所有</p>
  </footer>
</template>

<style>
body {
  margin: 0;
  font-family: var(--font-sans);
  color: var(--color-text);
}
#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
/* ===== 顶栏 ===== */
.topbar {
  display: flex;
  align-items: center;
  gap: 14px;
  height: 56px;
  padding: 0 20px;
  border-bottom: 1px solid var(--color-border-light);
  background: var(--bg-surface);
  backdrop-filter: saturate(1.8) blur(8px);
  position: sticky;
  top: 0;
  z-index: 20;
}
.burger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast);
}
.burger:hover {
  color: var(--color-primary);
  border-color: var(--color-primary-border);
}
.burger svg {
  width: 18px;
  height: 18px;
}
.brandbox {
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo {
  width: 26px;
  height: 26px;
}
.brandname {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: 0.01em;
}
.version {
  font-size: 11px;
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  padding: 1px 8px;
}
.spacer {
  flex: 1;
}
.userbox {
  display: flex;
  align-items: center;
  gap: 10px;
}
.uname {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.role-tag {
  font-size: 11px;
  color: var(--color-primary);
  background: var(--color-primary-light);
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-full);
  padding: 1px 8px;
}
.logout {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast);
}
.logout:hover {
  color: var(--color-error);
  border-color: var(--color-error-border);
}
/* ===== 侧边栏 ===== */
.sidebar {
  position: fixed;
  top: 56px;
  left: 0;
  bottom: 0;
  width: 224px;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border-right: 1px solid var(--color-border-light);
  transition: width var(--transition-base);
  overflow-x: hidden;
  z-index: 15;
}
.sidebar.collapsed {
  width: 60px;
}
.menu {
  flex: 1;
  overflow-y: auto;
  padding: 10px 8px 16px;
}
.group-label {
  margin: 12px 12px 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  white-space: nowrap;
}
.link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  margin: 2px 0;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: 13.5px;
  white-space: nowrap;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.link:hover {
  background: var(--bg-hover);
  color: var(--color-text);
}
.link.active {
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-weight: 600;
}
.link .icon {
  flex-shrink: 0;
  display: inline-flex;
  width: 20px;
  height: 20px;
}
.link .icon svg {
  width: 20px;
  height: 20px;
}
.sidebar.collapsed .link {
  justify-content: center;
  padding: 9px 0;
}
.sidebar.collapsed .text,
.sidebar.collapsed .group-label {
  display: none;
}
.sidebar-foot {
  padding: 10px 16px;
  font-size: 11px;
  color: var(--color-text-muted);
  border-top: 1px solid var(--color-border-light);
  white-space: nowrap;
}
/* ===== 内容区 ===== */
.content {
  margin-left: 224px;
  transition: margin-left var(--transition-base);
}
.content.collapsed {
  margin-left: 60px;
}
.footer {
  margin-left: 224px;
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-muted);
  transition: margin-left var(--transition-base);
}
/* 窄屏：侧栏常折叠为图标栏 */
@media (max-width: 1024px) {
  .sidebar {
    width: 60px;
  }
  .sidebar .text,
  .sidebar .group-label {
    display: none;
  }
  .sidebar .link {
    justify-content: center;
    padding: 9px 0;
  }
  .content,
  .footer {
    margin-left: 60px;
  }
  .topbar {
    padding: 0 12px;
  }
  .brandname,
  .version,
  .role-tag {
    display: none;
  }
}
@media (max-width: 480px) {
  .userbox .uname {
    display: none;
  }
}
</style>
