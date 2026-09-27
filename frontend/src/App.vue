<script setup lang="ts">
// 应用根组件：顶部导航 + 路由出口，页面布局在各 view 内实现
import { computed, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/store/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const links = [
  { to: '/', label: '运营总览' },
  { to: '/compass', label: '全景罗盘' },
  { to: '/metrics', label: '指标中心' },
  { to: '/ops', label: '运营参谋' },
  { to: '/data-import', label: '数据导入' },
  { to: '/data-sources', label: '数据源' },
  { to: '/marketing', label: '营销渠道' },
  { to: '/collect', label: '采集调度' },
  { to: '/storage', label: '存储适配' },
  { to: '/model', label: '模型中心' },
  { to: '/security-log', label: '安全日志' },
  { to: '/learning', label: '学习进化' },
  { to: '/digital-human', label: '数字人' },
  { to: '/commercial', label: '商业化' },
]

/** 登录页不展示导航栏 */
const showChrome = computed(() => route.name !== 'login')

onMounted(async () => {
  if (!auth.isLoggedIn) return
  try {
    await auth.loadProfile()
  } catch {
    // 令牌失效由 request 拦截器统一跳转登录页
  }
})

async function handleLogout() {
  await auth.logout()
  router.replace({ name: 'login' })
}
</script>

<template>
  <template v-if="showChrome">
    <header class="topbar">
      <div class="brandbox">
        <img class="logo" src="/favicon.ico" alt="运营智脑" />
        <span class="brandname">运营智脑</span>
      </div>
      <nav class="topnav">
        <RouterLink
          v-for="l in links"
          :key="l.to"
          :to="l.to"
          class="link"
          :class="{ active: route.path === l.to }"
        >
          {{ l.label }}
        </RouterLink>
      </nav>
      <div class="userbox">
        <span class="uname">{{ auth.displayName }}</span>
        <span v-if="auth.isSuperuser" class="role-tag">超级管理员</span>
        <span v-else-if="auth.roles.length" class="role-tag">{{ auth.roles.join(' / ') }}</span>
        <button class="logout" type="button" @click="handleLogout">退出</button>
      </div>
    </header>
    <RouterView />
  </template>
  <RouterView v-else />
  <footer class="footer">
    <p>BY LAOMENG网络工作室所有</p>
  </footer>
</template>

<style>
body {
  margin: 0;
  font-family: var(--font-sans);
  color: var(--color-text);
}
/* 页脚贴底：内容不足一屏时也停在视口底部（配合 .footer 的 margin-top:auto）；
   子项禁止压缩，避免长页面下顶栏/内容被 flex 压扁 */
#app {
  display: flex;
  flex-direction: column;
  height: auto;
  min-height: 100vh;
}
#app > * {
  width: 100%;
  flex-shrink: 0;
}
.topbar {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 0 32px;
  height: 56px;
  border-bottom: 1px solid var(--color-border-light);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: saturate(1.8) blur(8px);
  position: sticky;
  top: 0;
  z-index: 10;
}
.brandbox {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.brandbox .logo {
  width: 28px;
  height: 28px;
  border-radius: 6px;
}
.brandbox .brandname {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: var(--color-text);
}
.topnav {
  display: flex;
  align-items: center;
  flex: 1;
  gap: 4px;
  overflow-x: auto;
  scrollbar-width: none;
}
.topnav .link {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.topnav .link:hover {
  background: var(--color-bg-hover);
  color: var(--color-text);
}
.topnav .link.active {
  background: var(--color-primary-light);
  color: var(--color-primary);
}
.userbox {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}
.role-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-size: 11px;
  font-weight: 600;
}
.logout {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
}
.logout:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-light);
}
.footer {
  margin-top: auto;
  padding: 18px 32px 28px;
  border-top: 1px solid var(--color-border-light);
  text-align: center;
  font-size: 12px;
  color: var(--color-text-muted);
  letter-spacing: 0.4px;
}
.footer p {
  margin: 0;
}

/* ===== 响应式自适应：顶部导航 ===== */
.topnav {
  -webkit-overflow-scrolling: touch;
}
.topnav::-webkit-scrollbar {
  display: none;
}

@media (max-width: 1024px) {
  .topbar {
    gap: 16px;
    padding: 0 20px;
  }
}

@media (max-width: 768px) {
  .topbar {
    flex-wrap: wrap;
    gap: 8px;
    padding: 8px 12px;
    height: auto;
    min-height: 52px;
  }
  .brandbox {
    gap: 8px;
  }
  .brandbox .brandname {
    font-size: 14px;
  }
  .userbox {
    margin-left: auto;
  }
  .userbox .uname,
  .userbox .role-tag {
    display: none;
  }
  .topnav {
    flex-basis: 100%;
    order: 3;
    flex-wrap: wrap;
    row-gap: 2px;
    overflow-x: visible;
  }
  .topnav .link {
    padding: 6px 9px;
    font-size: 12.5px;
  }
  .footer {
    padding: 16px 16px 22px;
  }
}

@media (max-width: 480px) {
  .topbar {
    gap: 8px;
    padding: 0 10px;
  }
  .brandbox .logo {
    width: 24px;
    height: 24px;
  }
  .brandbox .brandname {
    font-size: 13px;
    letter-spacing: 0.2px;
  }
  .topnav .link {
    padding: 5px 8px;
    font-size: 12px;
  }
  .logout {
    padding: 5px 9px;
    font-size: 12px;
  }
  .footer {
    padding: 14px 12px 20px;
  }
}
</style>
