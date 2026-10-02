/* 运营智脑 OpsCompass - Service Worker
 * 策略：
 *  - 导航请求（HTML）：network-first，离线回退到缓存的 app shell，再回退 offline.html
 *  - 同源静态资源：stale-while-revalidate（先返回缓存，后台更新）
 *  - /api 与跨域请求：完全不拦截，始终走网络（避免缓存业务数据与鉴权响应）
 */
const CACHE_VERSION = 'v0.10.1'
const CACHE_NAME = `opscompass-static-${CACHE_VERSION}`

const APP_SHELL = '/index.html'
const OFFLINE_PAGE = '/offline.html'
const PRECACHE_URLS = [
  '/',
  APP_SHELL,
  OFFLINE_PAGE,
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-maskable-512.png',
  '/icons/apple-touch-icon.png',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME)
      // 单个资源失败不应导致整个安装失败
      await Promise.all(
        PRECACHE_URLS.map((url) =>
          cache.add(new Request(url, { cache: 'reload' })).catch(() => undefined),
        ),
      )
    })(),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys()
      await Promise.all(
        keys.filter((k) => k.startsWith('opscompass-') && k !== CACHE_NAME).map((k) => caches.delete(k)),
      )
      if (self.registration.navigationPreload) {
        try {
          await self.registration.navigationPreload.disable()
        } catch (e) {
          /* 忽略 */
        }
      }
      await self.clients.claim()
    })(),
  )
})

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

/** 判断是否属于需要跳过 SW 处理的请求 */
function isBypassed(request) {
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return true
  if (url.pathname.startsWith('/api/')) return true
  return false
}

/** 导航请求：network-first */
async function handleNavigate(request) {
  const cache = await caches.open(CACHE_NAME)
  try {
    const response = await fetch(request)
    if (response && response.ok) {
      cache.put(APP_SHELL, response.clone())
    }
    return response
  } catch (error) {
    const shell = (await cache.match(APP_SHELL)) || (await cache.match('/'))
    if (shell) return shell
    const offline = await cache.match(OFFLINE_PAGE)
    if (offline) return offline
    return new Response('离线且无可用缓存', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    })
  }
}

/** 静态资源：stale-while-revalidate */
async function handleStatic(request) {
  const cache = await caches.open(CACHE_NAME)
  const cached = await cache.match(request)
  const network = fetch(request)
    .then((response) => {
      if (response && response.ok && response.type === 'basic') {
        cache.put(request, response.clone())
      }
      return response
    })
    .catch(() => undefined)

  if (cached) return cached
  const response = await network
  if (response) return response
  return new Response('资源不可用', {
    status: 504,
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  })
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return
  if (isBypassed(request)) return

  if (request.mode === 'navigate') {
    event.respondWith(handleNavigate(request))
    return
  }

  const url = new URL(request.url)
  if (
    url.pathname.startsWith('/assets/') ||
    url.pathname.startsWith('/icons/') ||
    url.pathname === '/manifest.webmanifest' ||
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.svg') ||
    url.pathname.endsWith('.ico') ||
    url.pathname.endsWith('.woff2')
  ) {
    event.respondWith(handleStatic(request))
  }
})
