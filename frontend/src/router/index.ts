import { createRouter, createWebHistory } from 'vue-router'

import { getToken } from '@/api/request'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/Login.vue'),
      meta: { title: '登录', public: true },
    },
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { title: '运营总览' },
    },
    {
      path: '/metrics',
      name: 'metric-center',
      component: () => import('@/views/MetricCenter.vue'),
      meta: { title: '指标中心' },
    },
    {
      path: '/compass',
      name: 'compass',
      component: () => import('@/views/Compass.vue'),
      meta: { title: '全景罗盘' },
    },
    {
      path: '/ops',
      name: 'ops-center',
      component: () => import('@/views/OpsCenter.vue'),
      meta: { title: '运营参谋' },
    },
    {
      path: '/data-import',
      name: 'data-import',
      component: () => import('@/views/DataImport.vue'),
      meta: { title: '数据导入' },
    },
    {
      path: '/data-sources',
      name: 'data-source-center',
      component: () => import('@/views/DataSourceCenter.vue'),
      meta: { title: '数据源' },
    },
    {
      path: '/marketing',
      name: 'marketing-center',
      component: () => import('@/views/MarketingCenter.vue'),
      meta: { title: '营销渠道' },
    },
    {
      path: '/collect',
      name: 'collect-center',
      component: () => import('@/views/CollectCenter.vue'),
      meta: { title: '采集调度' },
    },
    {
      path: '/storage',
      name: 'storage-center',
      component: () => import('@/views/StorageCenter.vue'),
      meta: { title: '存储适配' },
    },
    {
      path: '/model',
      name: 'model-center',
      component: () => import('@/views/ModelCenter.vue'),
      meta: { title: '模型中心' },
    },
    {
      path: '/security-log',
      name: 'security-log',
      component: () => import('@/views/SecurityLog.vue'),
      meta: { title: '安全日志' },
    },
    {
      path: '/ai-governance',
      name: 'ai-governance',
      component: () => import('@/views/AiGovernance.vue'),
      meta: { title: 'AI 治理' },
    },
    {
      path: '/learning',
      name: 'learning',
      component: () => import('@/views/Learning.vue'),
      meta: { title: '学习进化' },
    },
  ],
})

/** 全局路由守卫：未登录访问受保护页面时跳转登录页，已登录访问登录页则回首页 */
router.beforeEach((to) => {
  const authed = Boolean(getToken())
  const isPublic = Boolean(to.meta.public)

  if (!isPublic && !authed) {
    return {
      name: 'login',
      query: to.fullPath && to.fullPath !== '/' ? { redirect: to.fullPath } : {},
    }
  }
  if (isPublic && authed && to.name === 'login') {
    return { path: '/' }
  }
  return true
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title ? `${title} · 运营智脑` : '运营智脑 · 让数据自动做出最优决策'
})

export default router
