import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import './styles/main.css'

createApp(App).use(createPinia()).use(router).mount('#app')

/** 注册 Service Worker（PWA）：仅生产构建注册，dev 环境跳过以免干扰 HMR */
function registerServiceWorker(): void {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js', { scope: '/' })
      .then((registration) => {
        // 更新场景：新版本安装完成且已有旧版本接管页面时，跳过等待并刷新一次
        registration.addEventListener('updatefound', () => {
          const installing = registration.installing
          if (!installing) return
          installing.addEventListener('statechange', () => {
            if (installing.state === 'installed' && navigator.serviceWorker.controller) {
              installing.postMessage({ type: 'SKIP_WAITING' })
            }
          })
        })

        if (navigator.serviceWorker.controller) {
          let refreshing = false
          navigator.serviceWorker.addEventListener('controllerchange', () => {
            if (refreshing) return
            refreshing = true
            window.location.reload()
          })
        }

        // 每小时检查一次新版本
        window.setInterval(
          () => void registration.update().catch(() => undefined),
          60 * 60 * 1000,
        )
      })
      .catch((error) => {
        console.warn('[PWA] Service Worker 注册失败：', error)
      })
  })
}

registerServiceWorker()
