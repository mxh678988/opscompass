<script setup lang="ts">
// 营销全渠道接入：渠道类型目录 / 渠道授权 / 投放任务 / 事件日志
import { computed, onMounted, reactive, ref } from 'vue'
import {
  authorizeChannel,
  createCampaign,
  createChannel,
  deleteCampaign,
  deleteChannel,
  executeCampaign,
  fetchCampaigns,
  fetchChannelEvents,
  fetchChannelTypes,
  fetchChannels,
  fetchMarketingOverview,
  revokeChannel,
  syncChannel,
  updateChannel,
  type ChannelCampaign,
  type ChannelEvent,
  type ChannelTypeItem,
  type MarketingChannel,
  type MarketingOverview,
} from '@/api/marketing'

const AUTH_MODES = [
  { value: 'oauth', label: 'OAuth 授权' },
  { value: 'apikey', label: 'API Key' },
  { value: 'cookie', label: 'Cookie' },
]

const CAMPAIGN_TYPES = [
  { value: 'content_publish', label: '内容发布' },
  { value: 'ad_delivery', label: '广告投放' },
  { value: 'promotion', label: '活动促销' },
  { value: 'data_sync', label: '数据同步' },
]

const STATUS_TEXT: Record<string, string> = {
  unauthorized: '未授权',
  authorized: '已授权',
  expired: '已过期',
  disabled: '已停用',
  draft: '草稿',
  pending: '待执行',
  running: '执行中',
  success: '已成功',
  failed: '已失败',
  canceled: '已取消',
}

const overview = ref<MarketingOverview | null>(null)
const types = ref<ChannelTypeItem[]>([])
const channels = ref<MarketingChannel[]>([])
const campaigns = ref<ChannelCampaign[]>([])
const events = ref<ChannelEvent[]>([])

const loading = ref(false)
const error = ref('')
const notice = ref('')
const saving = ref(false)
const editingId = ref<number | null>(null)
const authTarget = ref<MarketingChannel | null>(null)

const channelForm = reactive({
  channel_type: 'douyin',
  channel_name: '',
  account_name: '',
  auth_type: 'oauth',
  api_base: '',
  scopes: '',
  auto_publish: false,
  remark: '',
  credential: '',
})

const authForm = reactive({
  credential: '',
  auth_type: '',
  expires_at: '',
  scopes: '',
})

const campaignForm = reactive({
  channel_id: '' as string | number,
  name: '',
  campaign_type: 'content_publish',
  content_title: '',
  content_body: '',
  target_url: '',
  budget_yuan: '',
  schedule_at: '',
  dispatch_mode: 'manual',
})

const channelNameMap = computed(() => {
  const map: Record<number, string> = {}
  channels.value.forEach((item) => {
    map[item.id] = item.channel_name
  })
  return map
})

const authorizedChannels = computed(() => channels.value.filter((c) => c.status === 'authorized'))

function resetChannelForm() {
  Object.assign(channelForm, {
    channel_type: 'douyin',
    channel_name: '',
    account_name: '',
    auth_type: 'oauth',
    api_base: '',
    scopes: '',
    auto_publish: false,
    remark: '',
    credential: '',
  })
  editingId.value = null
}

function resetCampaignForm() {
  Object.assign(campaignForm, {
    channel_id: authorizedChannels.value[0]?.id ?? '',
    name: '',
    campaign_type: 'content_publish',
    content_title: '',
    content_body: '',
    target_url: '',
    budget_yuan: '',
    schedule_at: '',
    dispatch_mode: 'manual',
  })
}

function fillFromType(item: ChannelTypeItem) {
  channelForm.channel_type = item.channel_type
  channelForm.auth_type = item.auth_modes[0] ?? 'apikey'
  if (!channelForm.channel_name) channelForm.channel_name = item.name
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [ov, tp, ch, cp, ev] = await Promise.all([
      fetchMarketingOverview(),
      fetchChannelTypes(),
      fetchChannels({ page: 1, page_size: 100 }),
      fetchCampaigns({ page: 1, page_size: 100 }),
      fetchChannelEvents({ limit: 30 }),
    ])
    overview.value = ov.data
    types.value = tp.data ?? []
    channels.value = ch.data.items ?? []
    campaigns.value = cp.data.items ?? []
    events.value = ev.data ?? []
    if (!campaignForm.channel_id) resetCampaignForm()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '加载失败'
  } finally {
    loading.value = false
  }
}

async function submitChannel() {
  error.value = ''
  notice.value = ''
  if (!channelForm.channel_name.trim() || !channelForm.account_name.trim()) {
    error.value = '渠道名称与账号标识必填'
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateChannel(editingId.value, {
        channel_name: channelForm.channel_name.trim(),
        account_name: channelForm.account_name.trim(),
        auth_type: channelForm.auth_type,
        api_base: channelForm.api_base,
        scopes: channelForm.scopes,
        auto_publish: channelForm.auto_publish,
        remark: channelForm.remark,
      })
      notice.value = '渠道信息已更新'
    } else {
      const payload: Record<string, unknown> = {
        channel_type: channelForm.channel_type,
        channel_name: channelForm.channel_name.trim(),
        account_name: channelForm.account_name.trim(),
        auth_type: channelForm.auth_type,
        api_base: channelForm.api_base,
        scopes: channelForm.scopes,
        auto_publish: channelForm.auto_publish,
        remark: channelForm.remark,
      }
      if (channelForm.credential.trim()) payload.credential = channelForm.credential.trim()
      await createChannel(payload as any)
      notice.value = channelForm.credential.trim()
        ? '渠道已新增并完成授权（凭据已加密存储）'
        : '渠道已新增，请在列表中完成授权'
    }
    resetChannelForm()
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '保存失败'
  } finally {
    saving.value = false
  }
}

function editChannel(row: MarketingChannel) {
  editingId.value = row.id
  Object.assign(channelForm, {
    channel_type: row.channel_type,
    channel_name: row.channel_name,
    account_name: row.account_name,
    auth_type: row.auth_type,
    api_base: row.api_base ?? '',
    scopes: row.scopes ?? '',
    auto_publish: row.auto_publish,
    remark: row.remark ?? '',
    credential: '',
  })
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function openAuthorize(row: MarketingChannel) {
  authTarget.value = row
  Object.assign(authForm, {
    credential: '',
    auth_type: row.auth_type,
    expires_at: '',
    scopes: row.scopes ?? '',
  })
}

async function submitAuthorize() {
  if (!authTarget.value) return
  error.value = ''
  notice.value = ''
  if (!authForm.credential.trim()) {
    error.value = '请填写凭据（Access Token / API Key / Cookie）'
    return
  }
  saving.value = true
  try {
    await authorizeChannel(authTarget.value.id, {
      credential: authForm.credential.trim(),
      auth_type: authForm.auth_type,
      expires_at: authForm.expires_at,
      scopes: authForm.scopes,
    })
    notice.value = `渠道「${authTarget.value.channel_name}」授权成功，凭据已加密存储`
    authTarget.value = null
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '授权失败'
  } finally {
    saving.value = false
  }
}

async function doRevoke(row: MarketingChannel) {
  if (!window.confirm(`确认撤销渠道「${row.channel_name}」的授权并清除本地凭据？`)) return
  try {
    await revokeChannel(row.id)
    notice.value = '已撤销授权'
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '撤销失败'
  }
}

async function doSync(row: MarketingChannel) {
  try {
    await syncChannel(row.id)
    notice.value = `已触发「${row.channel_name}」数据同步`
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '同步失败'
  }
}

async function toggleChannel(row: MarketingChannel) {
  const next = row.status === 'disabled' ? 'unauthorized' : 'disabled'
  if (next === 'disabled' && !window.confirm(`确认停用渠道「${row.channel_name}」？停用后不再参与投放编排。`)) {
    return
  }
  try {
    await updateChannel(row.id, { status: next })
    notice.value = next === 'disabled' ? '渠道已停用' : '渠道已恢复启用'
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '操作失败'
  }
}

async function removeChannel(row: MarketingChannel) {
  if (!window.confirm(`确认删除渠道「${row.channel_name}」？其投放任务与事件日志将一并删除。`)) return
  try {
    await deleteChannel(row.id)
    notice.value = '渠道已删除'
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '删除失败'
  }
}

async function submitCampaign() {
  error.value = ''
  notice.value = ''
  if (!campaignForm.channel_id) {
    error.value = '请先选择目标渠道（仅已授权渠道可投放）'
    return
  }
  if (!campaignForm.name.trim()) {
    error.value = '任务名称必填'
    return
  }
  saving.value = true
  try {
    await createCampaign({
      channel_id: Number(campaignForm.channel_id),
      name: campaignForm.name.trim(),
      campaign_type: campaignForm.campaign_type,
      content_title: campaignForm.content_title,
      content_body: campaignForm.content_body,
      target_url: campaignForm.target_url,
      budget_cents: Math.round(Number(campaignForm.budget_yuan || 0) * 100),
      schedule_at: campaignForm.schedule_at,
      dispatch_mode: campaignForm.dispatch_mode,
    })
    notice.value = '投放任务已创建'
    resetCampaignForm()
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '创建失败'
  } finally {
    saving.value = false
  }
}

async function doExecute(row: ChannelCampaign) {
  try {
    const res = await executeCampaign(row.id)
    notice.value = `任务「${row.name}」本地编排完成（演练，未调用平台真实 API）：${res.data.status === 'success' ? '成功' : res.data.error_message}`
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '执行失败'
  }
}

async function removeCampaign(row: ChannelCampaign) {
  if (!window.confirm(`确认删除投放任务「${row.name}」？`)) return
  try {
    await deleteCampaign(row.id)
    notice.value = '投放任务已删除'
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '删除失败'
  }
}

function statusText(status: string): string {
  return STATUS_TEXT[status] ?? status
}

function authModeText(mode: string): string {
  return AUTH_MODES.find((m) => m.value === mode)?.label ?? mode
}

function campaignTypeText(type: string): string {
  return CAMPAIGN_TYPES.find((t) => t.value === type)?.label ?? type
}

onMounted(load)
</script>

<template>
  <main class="marketing">
    <header class="head">
      <h1>营销渠道</h1>
      <p class="subtitle">
        全渠道接入与投放编排：平台授权（凭据加密存储）、内容 / 广告 / 促销任务分发、渠道事件留痕
      </p>
    </header>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="notice" class="notice">{{ notice }}</p>

    <!-- 接入概览 -->
    <section class="panel">
      <h2>接入概览</h2>
      <div class="metrics">
        <div class="metric">
          <span class="label">已接入渠道</span>
          <strong>{{ overview?.channels_total ?? 0 }}</strong>
        </div>
        <div class="metric">
          <span class="label">已授权</span>
          <strong class="ok">{{ overview?.channels_authorized ?? 0 }}</strong>
        </div>
        <div class="metric">
          <span class="label">未授权 / 过期</span>
          <strong class="warn">
            {{ (overview?.channels_unauthorized ?? 0) + (overview?.channels_expired ?? 0) }}
          </strong>
        </div>
        <div class="metric">
          <span class="label">投放任务</span>
          <strong>{{ overview?.campaigns_total ?? 0 }}</strong>
        </div>
        <div class="metric">
          <span class="label">成功 / 待执行</span>
          <strong>{{ overview?.campaigns_success ?? 0 }} / {{ overview?.campaigns_pending ?? 0 }}</strong>
        </div>
        <div class="metric">
          <span class="label">渠道事件</span>
          <strong>{{ overview?.events_total ?? 0 }}</strong>
        </div>
      </div>
      <p v-if="overview?.covered_types?.length" class="hint">
        已覆盖平台：{{ types.filter((t) => t.connected > 0).map((t) => t.name).join('、') }}
      </p>
      <p v-else class="hint">尚未接入任何平台，可从下方渠道类型目录开始接入</p>
    </section>

    <!-- 渠道类型目录 -->
    <section class="panel">
      <h2>渠道类型目录（{{ types.length }}）</h2>
      <div class="types">
        <div v-for="item in types" :key="item.channel_type" class="type-card">
          <div class="type-head">
            <strong>{{ item.name }}</strong>
            <span class="tag">{{ item.category }}</span>
          </div>
          <p class="type-platform">{{ item.platform }}</p>
          <p class="type-meta">
            授权：{{ item.auth_modes.map((m) => authModeText(m)).join(' / ') }}
          </p>
          <p class="type-meta">能力：{{ item.abilities.join('、') }}</p>
          <div class="type-foot">
            <span class="count">已接入 {{ item.connected }} · 已授权 {{ item.authorized }}</span>
            <button @click="fillFromType(item)">接入该平台</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 渠道账号 -->
    <section class="panel">
      <h2>{{ editingId ? `编辑渠道：#${editingId}` : '新增渠道账号' }}</h2>
      <form class="form" @submit.prevent="submitChannel">
        <label>
          <span>平台类型 *</span>
          <select v-model="channelForm.channel_type" :disabled="!!editingId">
            <option v-for="item in types" :key="item.channel_type" :value="item.channel_type">
              {{ item.name }}
            </option>
          </select>
        </label>
        <label>
          <span>渠道名称 *</span>
          <input v-model="channelForm.channel_name" placeholder="如 抖音官方号" />
        </label>
        <label>
          <span>账号标识 *</span>
          <input v-model="channelForm.account_name" placeholder="如 laomeng_dy" />
        </label>
        <label>
          <span>授权方式</span>
          <select v-model="channelForm.auth_type">
            <option v-for="m in AUTH_MODES" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
        </label>
        <label>
          <span>接口网关</span>
          <input v-model="channelForm.api_base" placeholder="可选，如 https://open.douyin.com" />
        </label>
        <label>
          <span>授权范围</span>
          <input v-model="channelForm.scopes" placeholder="如 content_publish,data_sync" />
        </label>
        <label>
          <span>凭据（仅写入不回显）</span>
          <input
            v-model="channelForm.credential"
            type="password"
            :placeholder="editingId ? '编辑时不修改凭据' : '可直接粘贴 Token / Key，留空则先建后授权'"
          />
        </label>
        <label>
          <span>备注</span>
          <input v-model="channelForm.remark" placeholder="可选" />
        </label>
        <label class="check">
          <input v-model="channelForm.auto_publish" type="checkbox" />
          <span>允许自动发布</span>
        </label>
        <button class="primary" type="submit" :disabled="saving">
          {{ saving ? '保存中…' : editingId ? '保存修改' : '新增渠道' }}
        </button>
        <button v-if="editingId" type="button" @click="resetChannelForm">取消编辑</button>
      </form>
    </section>

    <section class="panel">
      <h2>渠道账号（{{ channels.length }}）</h2>
      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>渠道</th>
            <th>平台</th>
            <th>账号</th>
            <th>授权</th>
            <th>凭据</th>
            <th>状态</th>
            <th>最近同步</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in channels" :key="row.id">
            <td>{{ row.channel_name }}</td>
            <td class="mono">{{ row.channel_type }}</td>
            <td class="mono">{{ row.account_name }}</td>
            <td>{{ authModeText(row.auth_type) }}</td>
            <td class="mono">{{ row.credential_masked || '-' }}</td>
            <td>
              <span class="tag" :class="row.status">{{ statusText(row.status) }}</span>
            </td>
            <td class="mono">{{ row.last_sync_at || '-' }}</td>
            <td class="ops">
              <button @click="editChannel(row)">编辑</button>
              <button v-if="row.status !== 'authorized'" class="primary" @click="openAuthorize(row)">
                授权
              </button>
              <button v-else @click="doRevoke(row)">撤销授权</button>
              <button :disabled="row.status !== 'authorized'" @click="doSync(row)">同步</button>
              <button @click="toggleChannel(row)">
                {{ row.status === 'disabled' ? '启用' : '停用' }}
              </button>
              <button class="danger" @click="removeChannel(row)">删除</button>
            </td>
          </tr>
          <tr v-if="!channels.length && !loading">
            <td colspan="8" class="empty">暂无渠道，请先新增渠道账号</td>
          </tr>
        </tbody>
      </table>
      </div>
      <p v-if="loading" class="hint">加载中…</p>
    </section>

    <!-- 授权抽屉化内联表单 -->
    <section v-if="authTarget" class="panel auth-box">
      <h2>授权：{{ authTarget.channel_name }}（{{ authTarget.account_name }}）</h2>
      <p class="hint">
        凭据将以 Fernet 对称加密后落库，界面仅展示脱敏串；请使用平台开放平台签发的 Token / Key，勿填写账号密码。
      </p>
      <form class="form" @submit.prevent="submitAuthorize">
        <label>
          <span>凭据 *</span>
          <input v-model="authForm.credential" type="password" placeholder="Access Token / API Key / Cookie" />
        </label>
        <label>
          <span>授权方式</span>
          <select v-model="authForm.auth_type">
            <option v-for="m in AUTH_MODES" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
        </label>
        <label>
          <span>到期时间</span>
          <input v-model="authForm.expires_at" placeholder="如 2026-12-31 23:59:59（可选）" />
        </label>
        <label>
          <span>授权范围</span>
          <input v-model="authForm.scopes" placeholder="如 content_publish,data_sync" />
        </label>
        <button class="primary" type="submit" :disabled="saving">
          {{ saving ? '提交中…' : '确认授权' }}
        </button>
        <button type="button" @click="authTarget = null">取消</button>
      </form>
    </section>

    <!-- 投放任务 -->
    <section class="panel">
      <h2>新建投放任务</h2>
      <form class="form" @submit.prevent="submitCampaign">
        <label>
          <span>目标渠道 *</span>
          <select v-model="campaignForm.channel_id">
            <option value="" disabled>请选择已授权渠道</option>
            <option v-for="c in authorizedChannels" :key="c.id" :value="c.id">
              {{ c.channel_name }}（{{ c.channel_type }}）
            </option>
          </select>
        </label>
        <label>
          <span>任务名称 *</span>
          <input v-model="campaignForm.name" placeholder="如 中秋节礼盒短视频投放" />
        </label>
        <label>
          <span>任务类型</span>
          <select v-model="campaignForm.campaign_type">
            <option v-for="t in CAMPAIGN_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </label>
        <label>
          <span>内容标题</span>
          <input v-model="campaignForm.content_title" placeholder="可选" />
        </label>
        <label>
          <span>目标链接</span>
          <input v-model="campaignForm.target_url" placeholder="可选，落地页地址" />
        </label>
        <label>
          <span>预算（元）</span>
          <input v-model="campaignForm.budget_yuan" type="number" min="0" step="0.01" placeholder="可选" />
        </label>
        <label>
          <span>计划时间</span>
          <input v-model="campaignForm.schedule_at" placeholder="如 2026-09-30 20:00:00（可选）" />
        </label>
        <label>
          <span>分发模式</span>
          <select v-model="campaignForm.dispatch_mode">
            <option value="manual">手动执行</option>
            <option value="auto">排期自动</option>
          </select>
        </label>
        <label class="wide">
          <span>内容正文</span>
          <textarea v-model="campaignForm.content_body" rows="3" placeholder="投放文案 / 说明（可选）" />
        </label>
        <button class="primary" type="submit" :disabled="saving">
          {{ saving ? '创建中…' : '创建任务' }}
        </button>
      </form>
      <p class="hint">
        当前版本为接入骨架：执行任务仅完成本地编排与凭据校验（演练），不会调用平台真实 API，也不写入曝光 / 点击 / 转化数据。
      </p>
    </section>

    <section class="panel">
      <h2>投放任务（{{ campaigns.length }}）</h2>
      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>任务</th>
            <th>渠道</th>
            <th>类型</th>
            <th>预算</th>
            <th>分发</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in campaigns" :key="row.id">
            <td>{{ row.name }}</td>
            <td>{{ channelNameMap[row.channel_id] ?? `#${row.channel_id}` }}</td>
            <td>{{ campaignTypeText(row.campaign_type) }}</td>
            <td class="mono">{{ (row.budget_cents / 100).toFixed(2) }}</td>
            <td>{{ row.dispatch_mode === 'auto' ? '排期自动' : '手动执行' }}</td>
            <td>
              <span class="tag" :class="row.status">{{ statusText(row.status) }}</span>
            </td>
            <td class="ops">
              <button class="primary" @click="doExecute(row)">执行</button>
              <button class="danger" @click="removeCampaign(row)">删除</button>
            </td>
          </tr>
          <tr v-if="!campaigns.length && !loading">
            <td colspan="7" class="empty">暂无投放任务</td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>

    <!-- 事件日志 -->
    <section class="panel">
      <h2>渠道事件（最近 {{ events.length }} 条）</h2>
      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>级别</th>
            <th>类型</th>
            <th>渠道</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in events" :key="row.id">
            <td class="mono">{{ row.created_at ?? '-' }}</td>
            <td>
              <span class="tag" :class="row.level">{{ row.level }}</span>
            </td>
            <td class="mono">{{ row.event_type }}</td>
            <td>{{ channelNameMap[row.channel_id] ?? `#${row.channel_id}` }}</td>
            <td class="msg">{{ row.message }}</td>
          </tr>
          <tr v-if="!events.length && !loading">
            <td colspan="5" class="empty">暂无事件记录</td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>
  </main>
</template>

<style scoped>
.marketing { padding: 32px; max-width: 1400px; margin: 0 auto; }
.subtitle { color: var(--color-text-secondary); margin-bottom: 24px; font-size: 14px; }
.panel { border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 20px; margin-bottom: 20px; background: var(--color-bg); }
.panel h2 { font-size: 15px; font-weight: 600; color: var(--color-text); margin: 0 0 14px; }

.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.metric {
  border: 1px solid var(--color-border); border-radius: var(--radius-md, 8px);
  padding: 12px 14px; display: flex; flex-direction: column; gap: 6px;
  background: var(--color-bg-subtle);
}
.metric .label { font-size: 12px; color: var(--color-text-secondary); }
.metric strong { font-size: 20px; color: var(--color-text); }
.metric strong.ok { color: var(--color-success); }
.metric strong.warn { color: var(--color-warning, #d97706); }

.types { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
.type-card {
  border: 1px solid var(--color-border); border-radius: var(--radius-md, 8px);
  padding: 12px 14px; display: flex; flex-direction: column; gap: 6px;
}
.type-head { display: flex; align-items: center; justify-content: space-between; }
.type-platform { font-size: 12px; color: var(--color-text-muted); margin: 0; }
.type-meta { font-size: 12px; color: var(--color-text-secondary); margin: 0; }
.type-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; gap: 8px; }
.type-foot .count { font-size: 12px; color: var(--color-text-muted); }

.form { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px 16px; align-items: end; }
.form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--color-text-secondary); }
.form label.check { flex-direction: row; align-items: center; gap: 8px; }
.form label.wide { grid-column: 1 / -1; }
input, select, textarea {
  padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px;
  font-size: 14px; width: 100%; box-sizing: border-box; font-family: inherit;
}
input[type='checkbox'] { width: auto; }
input:disabled, select:disabled { background: var(--color-border-light); color: var(--color-text-muted); }

button { padding: 8px 14px; border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-bg); cursor: pointer; font-size: 13px; }
button.primary { background: var(--color-primary); border-color: var(--color-primary); color: var(--color-bg); }
button.primary:disabled, button:disabled { opacity: 0.6; cursor: not-allowed; }
button.danger { color: var(--color-error); border-color: var(--color-error-border); }

table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--color-border-light); }
th { color: var(--color-text-secondary); font-weight: 500; white-space: nowrap; }
td.mono, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
td.msg { white-space: normal; }
.ops { white-space: nowrap; }
.ops button { margin-right: 6px; }
.tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; background: var(--color-bg-subtle); color: var(--color-text-secondary); font-weight: 600; }
.tag.authorized, .tag.success, .tag.info { background: var(--color-success-light); color: var(--color-success); }
.tag.unauthorized, .tag.draft, .tag.pending { background: var(--color-bg-subtle); color: var(--color-text-secondary); }
.tag.disabled, .tag.expired, .tag.warning, .tag.failed, .tag.error { background: var(--color-error-light, #fee2e2); color: var(--color-error); }
.empty, .hint { color: var(--color-text-muted); font-size: 13px; }
.empty { text-align: center; }
.error { color: var(--color-error); font-size: 13px; margin: 8px 0; }
.notice { color: var(--color-success); font-size: 13px; margin: 8px 0; }
.auth-box { border-color: var(--color-primary-border); }

/* ===== P4 统一交互增强 ===== */
.panel { transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.panel:hover { border-color: var(--color-primary-border); }
tbody tr:hover td { background: var(--color-bg-hover); }
button { transition: background var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast); }
button:hover:not(:disabled) { border-color: var(--color-primary-border); }
button.primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.22);
}
.metric, .type-card { transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.metric:hover, .type-card:hover { border-color: var(--color-primary-border); box-shadow: var(--shadow-sm); }

    /* ===== 响应式自适应（窗口缩放） ===== */
    .type-head {
      flex-wrap: wrap;
    }
    @media (max-width: 1024px) {
      .marketing {
        padding: 20px 16px;
      }
    }
    @media (max-width: 768px) {
      .marketing {
        padding: 16px 12px;
      }
      .panel {
        padding: 16px;
      }
      .metrics {
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      }
      .types {
        grid-template-columns: 1fr;
      }
      .form {
        grid-template-columns: 1fr;
      }
      .auth-box {
        flex-wrap: wrap;
      }
    }
    @media (max-width: 480px) {
      .marketing {
        padding: 12px 10px;
      }
      .metrics {
        grid-template-columns: 1fr 1fr;
      }
    }
</style>
