<script setup lang="ts">
// 运营参谋：网站/网店 / 页面商品 / SEO-GEO / 媒体库 / 自媒体 / AI 智能设置
import { computed, onMounted, reactive, ref } from 'vue'
import {
  analyzeSocial,
  crawlSitePage,
  createMedia,
  createPage,
  createProduct,
  createSocialPost,
  createWebsite,
  deleteMedia,
  deleteProduct,
  fetchAiConfigs,
  fetchGeoTasks,
  fetchMedia,
  fetchPages,
  fetchProducts,
  fetchSeoTasks,
  fetchWebsites,
  generateContent,
  optimizeSocial,
  runGeoTask,
  runOpsAnalysis,
  runSeoTask,
  saveAiConfig,
  scheduleSocial,
  updateAiConfig,
  updatePage,
  updateProduct,
  updateWebsite,
  type CrawlResult,
  type GeoTask,
  type MediaItem,
  type ProductItem,
  type SeoTask,
  type Website,
  type WebsiteAiConfig,
  type WebsitePage,
} from '@/api/ops'

const SITE_TYPE_LABEL: Record<string, string> = {
  cms: '内容站',
  shop: '网店',
  blog: '博客',
  landing: '落地页',
  custom: '自定义',
}

const SEO_TASK_LABEL: Record<string, string> = {
  audit: '站点审计',
  generate_sitemap: '生成 Sitemap',
  generate_robots: '生成 Robots',
  content_audit: '内容审计',
  keyword_analysis: '关键词分析',
  link_audit: '外链审计',
}

const GEO_TASK_LABEL: Record<string, string> = {
  content_optimize: '内容优化',
  schema_markup: 'Schema 标记',
  ai_snippet: 'AI 摘要',
  structured_data: '结构化数据',
  local_seo: '本地 SEO',
}

const SETTING_LABEL: Record<string, string> = {
  seo_auto: 'SEO 自动化',
  content_auto: '内容自动化',
  seo_tone: 'SEO 语气',
  content_tone: '内容语气',
  publish_schedule: '定时发布',
  auto_sitemap: '自动 Sitemap',
  media_auto_tag: '媒体自动打标',
  auto_meta: '自动 Meta',
}

const PLATFORM_LABEL: Record<string, string> = {
  wechat: '微信公众号',
  weibo: '微博',
  douyin: '抖音',
  xiaohongshu: '小红书',
  zhihu: '知乎',
  bilibili: 'B 站',
}

const MEDIA_TYPE_LABEL: Record<string, string> = {
  image: '图片',
  video: '视频',
  audio: '音频',
  document: '文档',
  archive: '压缩包',
}

const SITE_STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  archived: '已归档',
}

const PUBLISH_LABEL: Record<string, string> = {
  draft: '草稿',
  scheduled: '待发布',
  published: '已发布',
  archived: '已归档',
}

/** ---------------------------------------------------------- 全局状态 */
const sites = ref<Website[]>([])
const activeSiteId = ref<number | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const busy = ref('')

const pages = ref<WebsitePage[]>([])
const products = ref<ProductItem[]>([])
const seoTasks = ref<SeoTask[]>([])
const geoTasks = ref<GeoTask[]>([])
const media = ref<MediaItem[]>([])
const aiConfigs = ref<WebsiteAiConfig[]>([])

const activeSite = computed(() => sites.value.find((s) => s.id === activeSiteId.value) ?? null)
const isShop = computed(() => activeSite.value?.site_type === 'shop')

function fail(e: any, fallback = '操作失败') {
  error.value = e?.response?.data?.detail ?? e?.message ?? fallback
}

async function withBusy(tag: string, fn: () => Promise<void>) {
  busy.value = tag
  error.value = ''
  notice.value = ''
  try {
    await fn()
  } catch (e: any) {
    fail(e)
  } finally {
    busy.value = ''
  }
}

/** ---------------------------------------------------------- 站点 */
const siteForm = reactive({
  site_name: '',
  site_url: '',
  site_type: 'cms',
  theme: '',
  description: '',
  ai_mode: 'local',
})

async function loadSites() {
  const res = await fetchWebsites()
  sites.value = res.data ?? []
  if (!sites.value.length) {
    activeSiteId.value = null
    return
  }
  if (!activeSiteId.value || !sites.value.some((s) => s.id === activeSiteId.value)) {
    activeSiteId.value = sites.value[0].id
  }
}

async function loadSiteData() {
  if (!activeSiteId.value) return
  const id = activeSiteId.value
  const [pg, pd, seo, geo, md, cf] = await Promise.all([
    fetchPages(id),
    fetchProducts(id),
    fetchSeoTasks(id),
    fetchGeoTasks(id),
    fetchMedia(id),
    fetchAiConfigs(id),
  ])
  pages.value = pg.data ?? []
  products.value = pd.data ?? []
  seoTasks.value = seo.data ?? []
  geoTasks.value = geo.data ?? []
  media.value = md.data ?? []
  aiConfigs.value = cf.data ?? []
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await loadSites()
    await loadSiteData()
  } catch (e: any) {
    fail(e, '加载失败')
  } finally {
    loading.value = false
  }
}

async function switchSite() {
  await withBusy('switch', loadSiteData)
}

async function submitSite() {
  if (!siteForm.site_name.trim() || !siteForm.site_url.trim()) {
    error.value = '请填写站点名称与站点 URL'
    return
  }
  await withBusy('site-create', async () => {
    const res = await createWebsite({ ...siteForm })
    sites.value = [...sites.value, res.data]
    activeSiteId.value = res.data.id
    siteForm.site_name = ''
    siteForm.site_url = ''
    siteForm.theme = ''
    siteForm.description = ''
    notice.value = `站点「${res.data.site_name}」已创建`
    await loadSiteData()
  })
}

async function toggleSiteStatus() {
  const site = activeSite.value
  if (!site) return
  const next = site.status === 'published' ? 'draft' : 'published'
  await withBusy('site-status', async () => {
    const res = await updateWebsite(site.id, { status: next })
    sites.value = sites.value.map((s) => (s.id === res.data.id ? res.data : s))
    notice.value = `站点状态已切换为「${SITE_STATUS_LABEL[next] ?? next}」`
  })
}

async function toggleSiteAi() {
  const site = activeSite.value
  if (!site) return
  await withBusy('site-ai', async () => {
    const res = await updateWebsite(site.id, { ai_enabled: !site.ai_enabled })
    sites.value = sites.value.map((s) => (s.id === res.data.id ? res.data : s))
    notice.value = `AI 运营已${res.data.ai_enabled ? '开启' : '关闭'}`
  })
}

/** ---------------------------------------------------------- 页面 */
const pageForm = reactive({
  title: '',
  slug: '',
  seo_keywords: '',
  seo_desc: '',
  content: '',
  publish_status: 'draft',
  content_level: 'L2',
})

async function submitPage() {
  if (!activeSiteId.value) {
    error.value = '请先创建站点'
    return
  }
  if (!pageForm.title.trim()) {
    error.value = '请填写页面标题'
    return
  }
  await withBusy('page-create', async () => {
    const res = await createPage(activeSiteId.value as number, { ...pageForm })
    pages.value = [res.data, ...pages.value]
    pageForm.title = ''
    pageForm.slug = ''
    pageForm.seo_keywords = ''
    pageForm.seo_desc = ''
    pageForm.content = ''
    notice.value = `页面「${res.data.title}」已创建（${PUBLISH_LABEL[res.data.publish_status] ?? res.data.publish_status}）`
  })
}

/** AI 内容生成/改写：按页面 SEO 关键词与语气生成新内容 */
const pageAiTone = ref('professional')
const pageAiBusy = ref(0)
const pageAiResult = ref<{ title: string; data: Record<string, any> } | null>(null)

async function aiRewritePage(page: WebsitePage) {
  if (!activeSiteId.value) return
  pageAiBusy.value = page.id
  error.value = ''
  notice.value = ''
  try {
    const keywords = (page.seo_keywords || '')
      .split(/[,，\s]+/)
      .map((k) => k.trim())
      .filter(Boolean)
    const res = await generateContent({
      website_id: activeSiteId.value as number,
      page_id: page.id,
      content_type: 'article',
      keywords,
      tone: pageAiTone.value,
      mode: 'local',
    })
    pageAiResult.value = { title: page.title, data: res.data }
    notice.value = `页面「${page.title}」AI 改写完成`
  } catch (e: any) {
    fail(e, 'AI 改写失败')
  } finally {
    pageAiBusy.value = 0
  }
}

/** 站内预览（P3 内置浏览器）：抓取同域页面并做 SEO 体检 */
const crawlPath = ref('')
const crawlBusyTag = ref('')
const crawlResult = ref<{ label: string; data: CrawlResult } | null>(null)

async function runCrawl(label: string, payload: { page_id?: number; path?: string }) {
  if (!activeSiteId.value) return
  crawlBusyTag.value = payload.page_id ? `page-${payload.page_id}` : 'home'
  error.value = ''
  notice.value = ''
  try {
    const res = await crawlSitePage(activeSiteId.value as number, payload)
    crawlResult.value = { label, data: res.data }
    notice.value = `已抓取「${label}」，HTTP ${res.data.status_code}`
  } catch (e: any) {
    fail(e, '站内预览失败')
  } finally {
    crawlBusyTag.value = ''
  }
}

function previewPage(page: WebsitePage) {
  return runCrawl(`${page.title} · /${page.slug}`, { page_id: page.id })
}

function previewHome() {
  const path = crawlPath.value.trim()
  return runCrawl(path ? `/${path}` : '站点首页', { path })
}

async function publishPage(page: WebsitePage) {
  const next = page.publish_status === 'published' ? 'draft' : 'published'
  await withBusy(`page-${page.id}`, async () => {
    const res = await updatePage(page.website_id, page.id, { publish_status: next })
    pages.value = pages.value.map((p) => (p.id === res.data.id ? res.data : p))
    notice.value = `页面「${res.data.title}」状态更新为「${PUBLISH_LABEL[next] ?? next}」`
  })
}

/** ---------------------------------------------------------- 商品 */
const productForm = reactive({
  name: '',
  price: 0,
  stock: 0,
  sku: '',
  description: '',
  status: 'draft',
})

async function submitProduct() {
  if (!activeSiteId.value) {
    error.value = '请先创建站点'
    return
  }
  if (!productForm.name.trim()) {
    error.value = '请填写商品名称'
    return
  }
  await withBusy('product-create', async () => {
    const res = await createProduct(activeSiteId.value as number, {
      ...productForm,
      price: Number(productForm.price) || 0,
    })
    products.value = [res.data, ...products.value]
    productForm.name = ''
    productForm.price = 0
    productForm.stock = 0
    productForm.sku = ''
    productForm.description = ''
    notice.value = `商品「${res.data.name}」已创建`
  })
}

async function toggleProductStatus(item: ProductItem) {
  const next = item.status === 'active' ? 'inactive' : 'active'
  await withBusy(`product-${item.id}`, async () => {
    const res = await updateProduct(item.website_id, item.id, { status: next })
    products.value = products.value.map((p) => (p.id === res.data.id ? res.data : p))
    notice.value = `商品「${res.data.name}」已${next === 'active' ? '上架' : '下架'}`
  })
}

async function removeProduct(item: ProductItem) {
  await withBusy(`product-del-${item.id}`, async () => {
    await deleteProduct(item.website_id, item.id)
    products.value = products.value.filter((p) => p.id !== item.id)
    notice.value = `商品「${item.name}」已删除`
  })
}

/** ---------------------------------------------------------- SEO / GEO */
const seoForm = reactive({ task_type: 'audit', ai_enabled: true })
const geoForm = reactive({ task_type: 'content_optimize', ai_enabled: true })

async function submitSeo() {
  if (!activeSiteId.value) {
    error.value = '请先创建站点'
    return
  }
  await withBusy('seo-run', async () => {
    const res = await runSeoTask(activeSiteId.value as number, { ...seoForm })
    seoTasks.value = [res.data, ...seoTasks.value]
    notice.value = `SEO 任务「${SEO_TASK_LABEL[res.data.task_type] ?? res.data.task_type}」执行完成`
  })
}

async function submitGeo() {
  if (!activeSiteId.value) {
    error.value = '请先创建站点'
    return
  }
  await withBusy('geo-run', async () => {
    const res = await runGeoTask(activeSiteId.value as number, { ...geoForm })
    geoTasks.value = [res.data, ...geoTasks.value]
    notice.value = `GEO 任务「${GEO_TASK_LABEL[res.data.task_type] ?? res.data.task_type}」执行完成`
  })
}

async function submitOpsAnalysis() {
  if (!activeSiteId.value) {
    error.value = '请先创建站点'
    return
  }
  await withBusy('ops-analyze', async () => {
    const res = await runOpsAnalysis({
      scope: 'seo',
      website_id: activeSiteId.value as number,
      max_insights: 8,
      mode: 'local',
    })
    opsAnalysis.value = res.data
    notice.value = 'AI 运营分析已完成'
  })
}

const opsAnalysis = ref<Record<string, any> | null>(null)

function parseResult(text: string) {
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return { raw: text }
  }
}

/** ---------------------------------------------------------- 媒体库 */
const mediaForm = reactive({
  media_type: 'image',
  file_url: '',
  file_name: '',
  folder: '',
  description: '',
  tags: '',
  content_level: 'L2',
})

async function submitMedia() {
  if (!activeSiteId.value) {
    error.value = '请先创建站点'
    return
  }
  if (!mediaForm.file_url.trim()) {
    error.value = '请填写媒体文件 URL'
    return
  }
  await withBusy('media-create', async () => {
    const tags = mediaForm.tags
      .split(/[,，\s]+/)
      .map((t) => t.trim())
      .filter(Boolean)
    const res = await createMedia(activeSiteId.value as number, {
      media_type: mediaForm.media_type,
      file_url: mediaForm.file_url,
      file_name: mediaForm.file_name || mediaForm.file_url.split('/').pop() || '',
      folder: mediaForm.folder,
      description: mediaForm.description,
      content_level: mediaForm.content_level,
      tags,
    })
    media.value = [res.data, ...media.value]
    mediaForm.file_url = ''
    mediaForm.file_name = ''
    mediaForm.description = ''
    mediaForm.tags = ''
    notice.value = '媒体资源已入库'
  })
}

async function removeMedia(item: MediaItem) {
  await withBusy(`media-del-${item.id}`, async () => {
    await deleteMedia(item.website_id, item.id)
    media.value = media.value.filter((m) => m.id !== item.id)
    notice.value = `媒体「${item.file_name || item.id}」已删除`
  })
}

function mediaTags(item: MediaItem) {
  if (!item.tags) return [] as string[]
  try {
    const parsed = JSON.parse(item.tags)
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return [item.tags]
  }
}

/** ---------------------------------------------------------- 自媒体 */
const socialForm = reactive({
  platform: 'wechat',
  content: '',
  tone: 'professional',
  scheduled_at: '',
})

const socialOptimize = ref<Record<string, any> | null>(null)
const socialSchedule = ref<Record<string, any> | null>(null)
const socialAnalytics = ref<Record<string, any> | null>(null)

async function submitSocial() {
  if (!activeSiteId.value) {
    error.value = '请先创建站点'
    return
  }
  if (!socialForm.content.trim()) {
    error.value = '请填写自媒体内容'
    return
  }
  await withBusy('social-post', async () => {
    const res = await createSocialPost(activeSiteId.value as number, {
      platform: socialForm.platform,
      content: socialForm.content,
      scheduled_at: socialForm.scheduled_at || undefined,
      ai_enabled: true,
    })
    notice.value = `发布任务已登记：${PLATFORM_LABEL[res.data.platform] ?? res.data.platform} · ${res.data.content_length} 字`
  })
}

async function submitOptimize() {
  if (!activeSiteId.value) {
    error.value = '请先创建站点'
    return
  }
  if (!socialForm.content.trim()) {
    error.value = '请先填写待优化的内容'
    return
  }
  await withBusy('social-optimize', async () => {
    const res = await optimizeSocial(activeSiteId.value as number, {
      platform: socialForm.platform,
      content: socialForm.content,
      tone: socialForm.tone,
      mode: 'local',
    })
    socialOptimize.value = res.data
    notice.value = 'AI 内容优化完成'
  })
}

async function submitSchedule() {
  if (!activeSiteId.value) {
    error.value = '请先创建站点'
    return
  }
  await withBusy('social-schedule', async () => {
    const posts = socialForm.content.trim()
      ? [{ content: socialForm.content, scheduled_at: socialForm.scheduled_at || undefined }]
      : []
    const res = await scheduleSocial(activeSiteId.value as number, {
      platform: socialForm.platform,
      posts,
    })
    socialSchedule.value = res.data
    notice.value = 'AI 已给出最佳发布时间建议'
  })
}

async function submitAnalytics() {
  if (!activeSiteId.value) {
    error.value = '请先创建站点'
    return
  }
  await withBusy('social-analytics', async () => {
    const res = await analyzeSocial(activeSiteId.value as number, { platform: socialForm.platform })
    socialAnalytics.value = res.data
    notice.value = '自媒体数据洞察已生成'
  })
}

/** ---------------------------------------------------------- AI 智能设置 */
const settingForm = reactive({
  setting_type: 'seo_auto',
  enabled: true,
  ai_model: '',
  note: '',
})

function settingConfig(type: string) {
  return aiConfigs.value.find((c) => c.setting_type === type) ?? null
}

async function toggleSetting(type: string) {
  const current = settingConfig(type)
  await withBusy(`setting-${type}`, async () => {
    if (!current) {
      const res = await saveAiConfig(activeSiteId.value as number, {
        setting_type: type,
        config_value: { note: '前端启用' },
        enabled: true,
      })
      aiConfigs.value = [...aiConfigs.value, res.data]
      notice.value = `已开启「${SETTING_LABEL[type] ?? type}」`
      return
    }
    const res = await updateAiConfig(current.id, {
      setting_type: type,
      config_value: { ...parseResult(current.config_value) },
      enabled: !current.enabled,
      ai_model: current.ai_model,
    })
    aiConfigs.value = aiConfigs.value.map((c) => (c.id === res.data.id ? res.data : c))
    notice.value = `「${SETTING_LABEL[type] ?? type}」已${res.data.enabled ? '开启' : '关闭'}`
  })
}

async function saveSetting() {
  if (!activeSiteId.value) {
    error.value = '请先创建站点'
    return
  }
  await withBusy('setting-save', async () => {
    const existing = settingConfig(settingForm.setting_type)
    if (existing) {
      const res = await updateAiConfig(existing.id, {
        setting_type: existing.setting_type,
        config_value: { note: settingForm.note || parseResult(existing.config_value)?.note || '' },
        enabled: settingForm.enabled,
        ai_model: settingForm.ai_model,
      })
      aiConfigs.value = aiConfigs.value.map((c) => (c.id === res.data.id ? res.data : c))
    } else {
      const res = await saveAiConfig(activeSiteId.value as number, {
        setting_type: settingForm.setting_type,
        config_value: { note: settingForm.note },
        enabled: settingForm.enabled,
        ai_model: settingForm.ai_model,
      })
      aiConfigs.value = [...aiConfigs.value, res.data]
    }
    settingForm.note = ''
    notice.value = `AI 设置「${SETTING_LABEL[settingForm.setting_type] ?? settingForm.setting_type}」已保存`
  })
}

function money(cent: number) {
  return `${((cent ?? 0) / 100).toFixed(2)} 元`
}

onMounted(load)
</script>

<template>
  <main class="ops">
    <header class="head">
      <h1>运营参谋</h1>
      <p class="subtitle">
        网站 / 网店 / 媒体库 / 自媒体 / SEO-GEO 一站运营：站点资产统一托管，AI 按权限自动执行 SEO 与内容优化
      </p>
    </header>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="notice" class="notice">{{ notice }}</p>

    <!-- 站点选择与概况 -->
    <section class="panel">
      <div class="panel-head">
        <h2>站点资产</h2>
        <div class="ops-line">
          <select v-model="activeSiteId" class="site-select" @change="switchSite">
            <option :value="null" disabled>选择站点</option>
            <option v-for="s in sites" :key="s.id" :value="s.id">
              {{ s.site_name }}（{{ SITE_TYPE_LABEL[s.site_type] ?? s.site_type }}）
            </option>
          </select>
          <button :disabled="!activeSite" @click="toggleSiteStatus">
            {{ activeSite?.status === 'published' ? '转草稿' : '发布站点' }}
          </button>
          <button :disabled="!activeSite" @click="toggleSiteAi">
            AI 运营{{ activeSite?.ai_enabled ? '已开启' : '已关闭' }}
          </button>
        </div>
      </div>

      <div v-if="activeSite" class="metrics">
        <div class="metric">
          <span class="label">站点地址</span>
          <strong class="mono ellipsis">{{ activeSite.site_url }}</strong>
        </div>
        <div class="metric">
          <span class="label">状态</span>
          <strong>{{ SITE_STATUS_LABEL[activeSite.status] ?? activeSite.status }}</strong>
        </div>
        <div class="metric">
          <span class="label">SEO / GEO 评分</span>
          <strong>{{ activeSite.seo_score }} / {{ activeSite.geo_score }}</strong>
        </div>
        <div class="metric">
          <span class="label">Sitemap</span>
          <strong>{{ activeSite.sitemap_generated ? '已生成' : '未生成' }}</strong>
        </div>
        <div class="metric">
          <span class="label">AI 模式</span>
          <strong class="mono">{{ activeSite.ai_mode }}</strong>
        </div>
      </div>
      <p v-else-if="!loading" class="empty">暂无站点，请先在下方创建</p>

      <h3 class="sub">新建站点</h3>
      <div class="form">
        <label>
          <span>站点名称</span>
          <input v-model="siteForm.site_name" placeholder="如 老孟严选" />
        </label>
        <label class="wide">
          <span>站点 URL</span>
          <input v-model="siteForm.site_url" placeholder="https://shop.example.com" />
        </label>
        <label>
          <span>类型</span>
          <select v-model="siteForm.site_type">
            <option v-for="(label, key) in SITE_TYPE_LABEL" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <label>
          <span>主题</span>
          <input v-model="siteForm.theme" placeholder="default" />
        </label>
        <label>
          <span>AI 模式</span>
          <select v-model="siteForm.ai_mode">
            <option value="local">本地模型</option>
            <option value="ai">云端 API</option>
          </select>
        </label>
        <label class="wide">
          <span>站点描述</span>
          <input v-model="siteForm.description" placeholder="一句话描述站点定位" />
        </label>
        <button class="primary" :disabled="busy === 'site-create'" @click="submitSite">
          {{ busy === 'site-create' ? '创建中…' : '创建站点' }}
        </button>
      </div>
    </section>

    <!-- 页面 / 文章 -->
    <section class="panel">
      <h2>页面与文章</h2>
      <div class="form">
        <label>
          <span>标题</span>
          <input v-model="pageForm.title" placeholder="页面标题" />
        </label>
        <label>
          <span>URL 路径</span>
          <input v-model="pageForm.slug" placeholder="about-us" />
        </label>
        <label>
          <span>SEO 关键词</span>
          <input v-model="pageForm.seo_keywords" placeholder="逗号分隔" />
        </label>
        <label>
          <span>内容分级</span>
          <select v-model="pageForm.content_level">
            <option value="L1">L1 公开</option>
            <option value="L2">L2 内部</option>
            <option value="L3">L3 敏感</option>
            <option value="L4">L4 机密</option>
          </select>
        </label>
        <label>
          <span>AI 语气</span>
          <select v-model="pageAiTone">
            <option value="professional">专业</option>
            <option value="friendly">亲和</option>
            <option value="humorous">幽默</option>
            <option value="formal">正式</option>
          </select>
        </label>
        <label class="wide">
          <span>SEO 描述</span>
          <input v-model="pageForm.seo_desc" placeholder="meta description" />
        </label>
        <label class="wide">
          <span>正文</span>
          <textarea v-model="pageForm.content" rows="3" placeholder="页面正文内容" />
        </label>
        <button class="primary" :disabled="busy === 'page-create' || !activeSiteId" @click="submitPage">
          {{ busy === 'page-create' ? '创建中…' : '创建页面' }}
        </button>
      </div>

      <div class="form">
        <label class="wide">
          <span>站内预览（仅同域抓取）</span>
          <input v-model="crawlPath" placeholder="留空抓取站点首页，如 blog/hello" />
        </label>
        <button :disabled="crawlBusyTag === 'home' || !activeSiteId" @click="previewHome">
          {{ crawlBusyTag === 'home' ? '抓取中…' : '抓取并体检' }}
        </button>
      </div>

      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>标题</th>
            <th>路径</th>
            <th>状态</th>
            <th>分级</th>
            <th>SEO 标题</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in pages" :key="p.id">
            <td>{{ p.title }}</td>
            <td class="mono ellipsis">/{{ p.slug }}</td>
            <td>
              <span class="tag" :class="p.publish_status === 'published' ? 'ok' : 'muted'">
                {{ PUBLISH_LABEL[p.publish_status] ?? p.publish_status }}
              </span>
            </td>
            <td>{{ p.content_level }}</td>
            <td class="ellipsis">{{ p.seo_title || '-' }}</td>
            <td class="row-ops">
              <button class="mini" :disabled="busy === `page-${p.id}`" @click="publishPage(p)">
                {{ p.publish_status === 'published' ? '转草稿' : '发布' }}
              </button>
              <button class="mini" :disabled="pageAiBusy === p.id" @click="aiRewritePage(p)">
                {{ pageAiBusy === p.id ? '改写中…' : 'AI 改写' }}
              </button>
              <button class="mini" :disabled="crawlBusyTag === `page-${p.id}`" @click="previewPage(p)">
                {{ crawlBusyTag === `page-${p.id}` ? '抓取中…' : '站内预览' }}
              </button>
            </td>
          </tr>
          <tr v-if="!pages.length">
            <td colspan="6" class="empty">暂无页面</td>
          </tr>
        </tbody>
      </table>
      </div>

      <div v-if="pageAiResult" class="result">
        <span class="tag ok">AI 改写</span>
        <strong>{{ pageAiResult.title }}</strong>
        <span class="reason mono wrap">{{ JSON.stringify(pageAiResult.data).slice(0, 260) }}</span>
      </div>

      <div v-if="crawlResult" class="result">
        <span class="tag ok">站内预览</span>
        <strong>{{ crawlResult.label }}</strong>
        <span class="reason mono wrap">HTTP {{ crawlResult.data.status_code }} · {{ crawlResult.data.elapsed_ms }}ms · {{ crawlResult.data.bytes }}B · {{ crawlResult.data.content_type || '未知类型' }}</span>
        <span class="reason mono wrap">最终地址: {{ crawlResult.data.final_url || crawlResult.data.url }}</span>
        <span class="reason mono wrap">
title {{ crawlResult.data.title.length }} 字 · description {{ crawlResult.data.meta_description.length }} 字 · H1 {{ crawlResult.data.h1.length }} 项 · 正文 {{ crawlResult.data.word_count }} 字
        </span>
        <span class="reason mono wrap">title: {{ crawlResult.data.title || '（缺失）' }}</span>
        <span class="reason mono wrap">description: {{ crawlResult.data.meta_description || '（缺失）' }}</span>
        <span class="reason mono wrap">h1: {{ crawlResult.data.h1.join(' / ') || '（缺失）' }}</span>
        <span class="reason">{{ crawlResult.data.text_preview }}</span>
        <div class="row-ops">
          <span v-for="d in crawlResult.data.diagnostics" :key="d.item" class="chip" :class="d.level === 'error' ? 'bad' : d.level === 'warn' ? 'warn' : 'ok'">
            {{ d.item }}：{{ d.message }}
          </span>
          <a class="mini" :href="crawlResult.data.final_url || crawlResult.data.url" target="_blank" rel="noreferrer">新窗口打开</a>
        </div>
      </div>
    </section>

    <!-- 商品（仅网店） -->
    <section class="panel">
      <h2>商品管理<span v-if="!isShop" class="hint-inline">（当前站点非网店类型，仍可登记商品）</span></h2>
      <div class="form">
        <label>
          <span>商品名称</span>
          <input v-model="productForm.name" placeholder="商品名称" />
        </label>
        <label>
          <span>价格（元）</span>
          <input v-model="productForm.price" type="number" min="0" step="0.01" />
        </label>
        <label>
          <span>库存</span>
          <input v-model="productForm.stock" type="number" min="0" />
        </label>
        <label>
          <span>SKU</span>
          <input v-model="productForm.sku" placeholder="SKU 编码" />
        </label>
        <button class="primary" :disabled="busy === 'product-create' || !activeSiteId" @click="submitProduct">
          {{ busy === 'product-create' ? '创建中…' : '创建商品' }}
        </button>
      </div>

      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>商品</th>
            <th>SKU</th>
            <th>价格</th>
            <th>库存</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in products" :key="item.id">
            <td>{{ item.name }}</td>
            <td class="mono">{{ item.sku || '-' }}</td>
            <td>{{ money(item.price) }}</td>
            <td>{{ item.stock }}</td>
            <td>
              <span class="tag" :class="item.status === 'active' ? 'ok' : 'muted'">
                {{ item.status === 'active' ? '已上架' : item.status === 'inactive' ? '已下架' : '草稿' }}
              </span>
            </td>
            <td class="row-ops">
              <button class="mini" :disabled="!!busy" @click="toggleProductStatus(item)">
                {{ item.status === 'active' ? '下架' : '上架' }}
              </button>
              <button class="mini danger" :disabled="!!busy" @click="removeProduct(item)">删除</button>
            </td>
          </tr>
          <tr v-if="!products.length">
            <td colspan="6" class="empty">暂无商品</td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>

    <!-- SEO / GEO -->
    <section class="panel">
      <div class="panel-head">
        <h2>SEO 与 GEO 任务</h2>
        <button :disabled="busy === 'ops-analyze' || !activeSiteId" @click="submitOpsAnalysis">
          {{ busy === 'ops-analyze' ? '分析中…' : 'AI 运营分析' }}
        </button>
      </div>

      <div class="form">
        <label>
          <span>SEO 任务类型</span>
          <select v-model="seoForm.task_type">
            <option v-for="(label, key) in SEO_TASK_LABEL" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <label class="check">
          <input v-model="seoForm.ai_enabled" type="checkbox" />
          <span>AI 增强</span>
        </label>
        <button class="primary" :disabled="busy === 'seo-run' || !activeSiteId" @click="submitSeo">
          {{ busy === 'seo-run' ? '执行中…' : '执行 SEO 任务' }}
        </button>

        <label>
          <span>GEO 任务类型</span>
          <select v-model="geoForm.task_type">
            <option v-for="(label, key) in GEO_TASK_LABEL" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <label class="check">
          <input v-model="geoForm.ai_enabled" type="checkbox" />
          <span>AI 增强</span>
        </label>
        <button class="primary" :disabled="busy === 'geo-run' || !activeSiteId" @click="submitGeo">
          {{ busy === 'geo-run' ? '执行中…' : '执行 GEO 任务' }}
        </button>
      </div>

      <div v-if="opsAnalysis" class="result">
        <span class="tag ok">{{ opsAnalysis.status }}</span>
        <strong>{{ opsAnalysis.site_name }}</strong>
        <span class="reason mono wrap">{{ JSON.stringify(opsAnalysis.seo_analysis ?? opsAnalysis).slice(0, 220) }}</span>
      </div>

      <h3 class="sub">SEO 任务记录</h3>
      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>任务</th>
            <th>状态</th>
            <th>AI 模型</th>
            <th>耗时</th>
            <th>结果摘要</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in seoTasks" :key="t.id">
            <td>{{ SEO_TASK_LABEL[t.task_type] ?? t.task_type }}</td>
            <td>
              <span class="tag" :class="t.status === 'success' ? 'ok' : t.status === 'failed' ? 'bad' : 'warn'">
                {{ t.status }}
              </span>
            </td>
            <td class="mono">{{ t.ai_model || '-' }}</td>
            <td>{{ t.duration_ms }} ms</td>
            <td class="ellipsis" :title="JSON.stringify(parseResult(t.result))">{{ JSON.stringify(parseResult(t.result)).slice(0, 120) }}</td>
          </tr>
          <tr v-if="!seoTasks.length">
            <td colspan="5" class="empty">暂无 SEO 任务</td>
          </tr>
        </tbody>
      </table>
      </div>

      <h3 class="sub">GEO 任务记录</h3>
      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>任务</th>
            <th>状态</th>
            <th>目标页面</th>
            <th>结果摘要</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in geoTasks" :key="t.id">
            <td>{{ GEO_TASK_LABEL[t.task_type] ?? t.task_type }}</td>
            <td>
              <span class="tag" :class="t.status === 'success' ? 'ok' : t.status === 'failed' ? 'bad' : 'warn'">
                {{ t.status }}
              </span>
            </td>
            <td class="mono ellipsis">{{ t.target_page_ids || '-' }}</td>
            <td class="ellipsis" :title="JSON.stringify(parseResult(t.result))">{{ JSON.stringify(parseResult(t.result)).slice(0, 120) }}</td>
          </tr>
          <tr v-if="!geoTasks.length">
            <td colspan="4" class="empty">暂无 GEO 任务</td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>

    <!-- 媒体库 -->
    <section class="panel">
      <h2>媒体库</h2>
      <div class="form">
        <label>
          <span>类型</span>
          <select v-model="mediaForm.media_type">
            <option v-for="(label, key) in MEDIA_TYPE_LABEL" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <label class="wide">
          <span>文件 URL</span>
          <input v-model="mediaForm.file_url" placeholder="https://cdn.example.com/banner.png" />
        </label>
        <label>
          <span>文件名</span>
          <input v-model="mediaForm.file_name" placeholder="banner.png" />
        </label>
        <label>
          <span>文件夹</span>
          <input v-model="mediaForm.folder" placeholder="banners" />
        </label>
        <label>
          <span>标签</span>
          <input v-model="mediaForm.tags" placeholder="逗号分隔" />
        </label>
        <label>
          <span>内容分级</span>
          <select v-model="mediaForm.content_level">
            <option value="L1">L1 公开</option>
            <option value="L2">L2 内部</option>
            <option value="L3">L3 敏感</option>
            <option value="L4">L4 机密</option>
          </select>
        </label>
        <button class="primary" :disabled="busy === 'media-create' || !activeSiteId" @click="submitMedia">
          {{ busy === 'media-create' ? '入库中…' : '登记媒体' }}
        </button>
      </div>

      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>文件</th>
            <th>类型</th>
            <th>大小</th>
            <th>文件夹</th>
            <th>标签</th>
            <th>分级</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in media" :key="m.id">
            <td class="ellipsis">{{ m.file_name || m.file_url }}</td>
            <td>{{ MEDIA_TYPE_LABEL[m.media_type] ?? m.media_type }}</td>
            <td>{{ m.file_size ? `${(m.file_size / 1024).toFixed(1)} KB` : '-' }}</td>
            <td class="mono">{{ m.folder || '-' }}</td>
            <td>
              <span v-for="tag in mediaTags(m)" :key="tag" class="chip">{{ tag }}</span>
              <span v-if="!mediaTags(m).length">-</span>
            </td>
            <td>{{ m.content_level }}</td>
            <td>
              <button class="mini danger" :disabled="!!busy" @click="removeMedia(m)">删除</button>
            </td>
          </tr>
          <tr v-if="!media.length">
            <td colspan="7" class="empty">暂无媒体资源</td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>

    <!-- 自媒体 -->
    <section class="panel">
      <h2>自媒体分发</h2>
      <div class="form">
        <label>
          <span>平台</span>
          <select v-model="socialForm.platform">
            <option v-for="(label, key) in PLATFORM_LABEL" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <label>
          <span>风格</span>
          <select v-model="socialForm.tone">
            <option value="professional">专业</option>
            <option value="friendly">亲和</option>
            <option value="humorous">幽默</option>
            <option value="formal">正式</option>
          </select>
        </label>
        <label>
          <span>计划发布时间</span>
          <input v-model="socialForm.scheduled_at" type="datetime-local" />
        </label>
        <label class="wide">
          <span>内容</span>
          <textarea v-model="socialForm.content" rows="3" placeholder="待分发的自媒体文案" />
        </label>
        <button class="primary" :disabled="busy === 'social-post' || !activeSiteId" @click="submitSocial">
          {{ busy === 'social-post' ? '登记中…' : '登记发布' }}
        </button>
        <button :disabled="busy === 'social-optimize' || !activeSiteId" @click="submitOptimize">
          {{ busy === 'social-optimize' ? '优化中…' : 'AI 优化文案' }}
        </button>
        <button :disabled="busy === 'social-schedule' || !activeSiteId" @click="submitSchedule">
          {{ busy === 'social-schedule' ? '排期中…' : 'AI 智能排期' }}
        </button>
        <button :disabled="busy === 'social-analytics' || !activeSiteId" @click="submitAnalytics">
          {{ busy === 'social-analytics' ? '分析中…' : 'AI 数据洞察' }}
        </button>
      </div>

      <div v-if="socialOptimize" class="result">
        <span class="tag ok">优化建议</span>
        <span class="reason mono wrap">{{ JSON.stringify(socialOptimize).slice(0, 260) }}</span>
      </div>
      <div v-if="socialSchedule" class="result">
        <span class="tag ok">发布排期</span>
        <span class="reason mono wrap">{{ JSON.stringify(socialSchedule).slice(0, 260) }}</span>
      </div>
      <div v-if="socialAnalytics" class="result">
        <span class="tag ok">数据洞察</span>
        <span class="reason mono wrap">{{ JSON.stringify(socialAnalytics).slice(0, 260) }}</span>
      </div>
    </section>

    <!-- AI 智能设置 -->
    <section class="panel">
      <h2>AI 智能设置</h2>
      <p class="hint">站点级 AI 自动化开关：用于 SEO、内容生成、定时发布与媒体打标等环节。</p>

      <ul class="settings">
        <li v-for="(label, key) in SETTING_LABEL" :key="key">
          <div class="setting-main">
            <strong>{{ label }}</strong>
            <span class="mono setting-type">{{ key }}</span>
            <span v-if="settingConfig(key)" class="tag" :class="settingConfig(key)?.enabled ? 'ok' : 'muted'">
              {{ settingConfig(key)?.enabled ? '已开启' : '已关闭' }}
            </span>
            <span v-else class="tag muted">未配置</span>
          </div>
          <div class="setting-detail">
            <span class="mono ellipsis">
              {{ settingConfig(key)?.config_value ?? '{}' }}
            </span>
            <button class="mini" :disabled="!!busy" @click="toggleSetting(key)">
              {{ settingConfig(key)?.enabled ? '关闭' : '开启' }}
            </button>
          </div>
        </li>
      </ul>

      <h3 class="sub">新增 / 覆盖配置</h3>
      <div class="form">
        <label>
          <span>配置项</span>
          <select v-model="settingForm.setting_type">
            <option v-for="(label, key) in SETTING_LABEL" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <label>
          <span>AI 模型</span>
          <input v-model="settingForm.ai_model" placeholder="留空用默认模型" />
        </label>
        <label class="check">
          <input v-model="settingForm.enabled" type="checkbox" />
          <span>启用</span>
        </label>
        <label class="wide">
          <span>备注 / 参数说明</span>
          <input v-model="settingForm.note" placeholder="如 自动生成 meta 描述，长度 120 字以内" />
        </label>
        <button class="primary" :disabled="busy === 'setting-save' || !activeSiteId" @click="saveSetting">
          {{ busy === 'setting-save' ? '保存中…' : '保存配置' }}
        </button>
      </div>
    </section>

    <p v-if="loading" class="hint">加载中…</p>
  </main>
</template>

<style scoped>
.ops { padding: 32px; max-width: 1400px; margin: 0 auto; }
.subtitle { color: var(--color-text-secondary); margin-bottom: 24px; font-size: 14px; }
.panel { border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 20px; margin-bottom: 20px; background: var(--color-bg); }
.panel h2 { font-size: 15px; font-weight: 600; color: var(--color-text); margin: 0 0 14px; }
.panel-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.panel-head h2 { margin: 0; }
.sub { font-size: 14px; margin: 22px 0 10px; color: var(--color-text); }
.hint-inline { font-size: 12px; color: var(--color-text-muted); font-weight: 400; margin-left: 6px; }
.ops-line { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.site-select { min-width: 220px; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 14px 0 6px; }
.metric { border: 1px solid var(--color-border-light); border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; }
.metric .label { font-size: 12px; color: var(--color-text-secondary); }
.form { display: flex; flex-wrap: wrap; gap: 12px 16px; align-items: end; margin-bottom: 12px; }
.form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--color-text-secondary); min-width: 180px; }
.form label.wide { flex: 1; min-width: 260px; }
select, input, textarea { padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; width: 100%; box-sizing: border-box; font-family: inherit; }
textarea { resize: vertical; }
button { padding: 8px 14px; border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-bg); cursor: pointer; font-size: 13px; }
button.primary { background: var(--color-primary); border-color: var(--color-primary); color: var(--color-bg); }
button:disabled { opacity: 0.6; cursor: not-allowed; }
button.mini { padding: 4px 10px; font-size: 12px; }
button.mini.danger { color: var(--color-error); border-color: var(--color-error-border); }
table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 6px; }
th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--color-border-light); }
th { color: var(--color-text-secondary); font-weight: 500; white-space: nowrap; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.ellipsis { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; background: var(--color-bg-subtle); color: var(--color-text-muted); }
.tag.ok { background: var(--color-success-light); color: var(--color-success); }
.tag.warn { background: var(--color-warning-light); color: var(--color-warning); }
.tag.bad { background: var(--color-error-light); color: var(--color-error); }
.tag.muted { background: var(--color-bg-subtle); color: var(--color-text-muted); }
.chip { display: inline-block; padding: 2px 8px; border-radius: 10px; background: var(--color-primary-light); color: var(--color-primary); font-size: 12px; margin: 0 6px 4px 0; }
.chip.ok { background: var(--color-success-light); color: var(--color-success); }
.chip.warn { background: var(--color-warning-light); color: var(--color-warning); }
.chip.bad { background: var(--color-error-light); color: var(--color-error); }
.check { flex-direction: row !important; align-items: center; gap: 6px !important; min-width: auto !important; }
.check input { width: auto; }
.result { display: flex; align-items: flex-start; gap: 10px; flex-wrap: wrap; font-size: 13px; padding: 10px 12px; border: 1px solid var(--color-border-light); background: var(--color-bg-subtle); border-radius: 8px; margin: 8px 0; }
.result .reason { color: var(--color-text-secondary); white-space: pre-wrap; word-break: break-word; max-height: 180px; overflow: auto; }
.row-ops { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.row-ops a.mini { font-size: 12px; color: var(--color-primary); }
.settings { list-style: none; margin: 10px 0 0; padding: 0; }
.settings li { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; border: 1px solid var(--color-border-light); border-radius: 8px; margin-bottom: 8px; }
.setting-main { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.setting-type { font-size: 12px; color: var(--color-text-muted); }
.setting-detail { display: flex; align-items: center; gap: 10px; max-width: 46%; font-size: 12px; color: var(--color-text-secondary); }
.empty, .hint { color: var(--color-text-muted); font-size: 13px; }
.error { color: var(--color-error); margin: 8px 0; font-size: 13px; }
.notice { color: var(--color-success); margin: 8px 0; font-size: 13px; }

/* ===== P4 统一交互增强 ===== */
.panel {
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.panel:hover {
  border-color: var(--color-primary-border);
}
tbody tr:hover td {
  background: var(--color-bg-hover);
}
button {
  transition: background var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast);
}
button:hover:not(:disabled) {
  border-color: var(--color-primary-border);
}
button.primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.22);
}
.tag {
  font-weight: 600;
}
.metrics .metric,
.engines .engine {
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.metrics .metric:hover,
.engines .engine:hover {
  border-color: var(--color-primary-border);
  box-shadow: var(--shadow-sm);
}

    /* ===== 响应式自适应（窗口缩放） ===== */
    .panel-head {
      flex-wrap: wrap;
    }
    .ops-line {
      flex-wrap: wrap;
    }
    .row-ops {
      flex-wrap: wrap;
    }
    @media (max-width: 1024px) {
      .ops {
        padding: 20px 16px;
      }
      .setting-detail {
        max-width: 100%;
      }
    }
    @media (max-width: 768px) {
      .ops {
        padding: 16px 12px;
      }
      .panel {
        padding: 16px;
      }
      .metrics {
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      }
      .form label,
      .form label.wide {
        min-width: 0;
        flex: 1 1 100%;
      }
      .site-select {
        min-width: 0;
        width: 100%;
      }
      .ellipsis {
        max-width: 160px;
      }
      .setting-detail {
        max-width: 100%;
      }
      .settings li {
        flex-direction: column;
        align-items: flex-start;
        gap: 6px;
      }
    }
    @media (max-width: 480px) {
      .ops {
        padding: 12px 10px;
      }
      .ellipsis {
        max-width: 120px;
      }
      .metrics {
        grid-template-columns: 1fr 1fr;
      }
    }
</style>
