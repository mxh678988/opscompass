<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  disablePlugin,
  enablePlugin,
  fetchPluginDetail,
  fetchPlugins,
  installPlugin,
  uninstallPlugin,
  type PluginItem,
} from '@/api/plugin'

const items = ref<PluginItem[]>([])
const total = ref(0)
const loading = ref(false)
const acting = ref<Record<string, boolean>>({})
const msg = reactive({ type: '', text: '' })

const filters = reactive({
  keyword: '',
  kind: '' as '' | 'official' | 'community',
  state: '' as '' | PluginItem['state'],
})
const page = ref(1)
const pageSize = ref(20)

const detail = ref<PluginItem | null>(null)
const showDetail = ref(false)
const detailLoading = ref(false)

const STATS = [
  { key: '', label: '全部' },
  { key: 'official', label: '官方' },
  { key: 'community', label: '社区' },
]
const STATE_LABEL: Record<string, string> = {
  discovered: '未安装',
  installed: '已安装',
  enabled: '已启用',
  disabled: '已禁用',
  uninstalled: '已卸载',
}
const STATE_CLS: Record<string, string> = {
  discovered: 'muted',
  installed: 'info',
  enabled: 'ok',
  disabled: 'warn',
  uninstalled: 'muted',
}

const filteredItems = computed(() => items.value)

function tip(type: string, text: string) {
  msg.type = type
  msg.text = text
}

function errText(e: any): string {
  return e?.response?.data?.message || e?.message || '请求失败'
}

function kindLabel(kind?: string) {
  return kind === 'official' ? '官方' : kind === 'community' ? '社区' : '-'
}

function stateLabel(state?: string) {
  return state ? STATE_LABEL[state] ?? state : '-'
}

function stateCls(state?: string) {
  return state ? STATE_CLS[state] ?? 'muted' : 'muted'
}

function permLabel(p: any): string {
  const code = typeof p === 'string' ? p : (p?.code ?? p?.name ?? '')
  if (!code) return '-'
  return String(code).split(':').pop() ?? code
}

function permKey(p: any): string {
  const code = typeof p === 'string' ? p : p?.code
  return code ?? ''
}

async function load() {
  loading.value = true
  try {
    const res = await fetchPlugins({
      keyword: filters.keyword.trim() || undefined,
      kind: filters.kind || undefined,
      state: filters.state || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = res.data?.items ?? []
    total.value = res.data?.total ?? 0
  } catch (e) {
    tip('error', `插件列表加载失败：${errText(e)}`)
  } finally {
    loading.value = false
  }
}

function resetPage() {
  page.value = 1
  load()
}

async function openDetail(item: PluginItem) {
  showDetail.value = true
  detail.value = item
  detailLoading.value = true
  try {
    const res = await fetchPluginDetail(item.plugin_id)
    detail.value = res.data
  } catch (e) {
    tip('error', `插件详情加载失败：${errText(e)}`)
  } finally {
    detailLoading.value = false
  }
}

async function run(action: (id: string) => Promise<any>, item: PluginItem, okText: string) {
  acting.value[item.plugin_id] = true
  try {
    const res = await action(item.plugin_id)
    tip('ok', `${item.name} ${okText}成功`)
    if (detail.value?.plugin_id === item.plugin_id) {
      detail.value.state = res.data?.state ?? detail.value.state
    }
    await load()
  } catch (e) {
    tip('error', `${item.name} ${okText}失败：${errText(e)}`)
  } finally {
    acting.value[item.plugin_id] = false
  }
}

function onInstall(item: PluginItem) {
  run(installPlugin, item, '安装')
}
function onEnable(item: PluginItem) {
  run(enablePlugin, item, '启用')
}
function onDisable(item: PluginItem) {
  run(disablePlugin, item, '禁用')
}
function onUninstall(item: PluginItem) {
  run(uninstallPlugin, item, '卸载')
}

function canInstall(item: PluginItem) {
  return item.state === 'discovered' || item.state === 'uninstalled'
}
function canEnable(item: PluginItem) {
  return item.state === 'disabled' || item.state === 'installed'
}
function canDisable(item: PluginItem) {
  return item.state === 'enabled'
}
function canUninstall(item: PluginItem) {
  return item.state === 'installed' || item.state === 'enabled' || item.state === 'disabled'
}

onMounted(load)
</script>

<template>
  <div class="page plugin-page">
    <div class="page-head">
      <h2>插件市场</h2>
      <p class="sub">社区插件上架、安装、启停与卸载，扩展运营智脑能力</p>
    </div>

    <div v-if="msg.text" class="flash" :class="msg.type === 'ok' ? 'flash-ok' : 'flash-err'">
      {{ msg.text }}
    </div>

    <div class="panel">
      <div class="toolbar">
        <div class="seg">
          <button
            v-for="s in STATS"
            :key="s.key"
            type="button"
            class="seg-btn"
            :class="{ active: filters.kind === s.key }"
            @click="filters.kind = s.key as any; resetPage()"
          >
            {{ s.label }}
          </button>
        </div>
        <div class="toolbar-right">
          <select
            v-model="filters.state"
            class="input select"
            @change="resetPage()"
          >
            <option value="">全部状态</option>
            <option value="discovered">未安装</option>
            <option value="installed">已安装</option>
            <option value="enabled">已启用</option>
            <option value="disabled">已禁用</option>
            <option value="uninstalled">已卸载</option>
          </select>
          <input
            v-model="filters.keyword"
            class="input search"
            type="search"
            placeholder="搜索插件名称 / ID"
            @keyup.enter="resetPage()"
          />
          <button type="button" class="btn" :disabled="loading" @click="resetPage()">查询</button>
          <button type="button" class="btn ghost" :disabled="loading" @click="filters.keyword = ''; filters.state = ''; resetPage()">
            重置
          </button>
        </div>
      </div>

      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="!filteredItems.length" class="empty">
        暂无插件。将插件 manifest 放入 backend/plugins/ 目录后刷新可见。
      </div>
      <div v-else class="plugin-grid">
        <div v-for="item in filteredItems" :key="item.plugin_id" class="plugin-card">
          <div class="plugin-card-head">
            <span class="plugin-name">{{ item.name }}</span>
            <span class="tag" :class="item.kind === 'official' ? 'tag-primary' : 'tag-info'">
              {{ kindLabel(item.kind) }}
            </span>
          </div>
          <div class="plugin-meta">
            <span>ID: <code>{{ item.plugin_id }}</code></span>
            <span>v{{ item.version }}</span>
          </div>
          <div class="plugin-perms">
            <span v-for="p in (item.permissions ?? []).slice(0, 3)" :key="permKey(p)" class="perm-tag">
              {{ permLabel(p) }}
            </span>
            <span v-if="(item.permissions ?? []).length > 3" class="perm-more">
              +{{ (item.permissions ?? []).length - 3 }}
            </span>
          </div>
          <div class="plugin-card-foot">
            <span class="state" :class="stateCls(item.state)">{{ stateLabel(item.state) }}</span>
            <div class="actions">
              <button type="button" class="btn mini ghost" :disabled="detailLoading" @click="openDetail(item)">详情</button>
              <button
                v-if="canInstall(item)"
                type="button"
                class="btn mini"
                :disabled="acting[item.plugin_id]"
                @click="onInstall(item)"
              >安装</button>
              <button
                v-else-if="canEnable(item)"
                type="button"
                class="btn mini"
                :disabled="acting[item.plugin_id]"
                @click="onEnable(item)"
              >启用</button>
              <button
                v-else-if="canDisable(item)"
                type="button"
                class="btn mini warn"
                :disabled="acting[item.plugin_id]"
                @click="onDisable(item)"
              >禁用</button>
              <button
                v-if="canUninstall(item)"
                type="button"
                class="btn mini danger"
                :disabled="acting[item.plugin_id]"
                @click="onUninstall(item)"
              >卸载</button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="total > pageSize" class="pager">
        <button type="button" class="btn ghost" :disabled="page <= 1" @click="page--; load()">上一页</button>
        <span class="pager-info">{{ page }} / {{ Math.ceil(total / pageSize) }} · 共 {{ total }} 个</span>
        <button
          type="button"
          class="btn ghost"
          :disabled="page >= Math.ceil(total / pageSize)"
          @click="page++; load()"
        >下一页</button>
      </div>
    </div>

    <div v-if="showDetail" class="modal-mask" @click.self="showDetail = false">
      <div class="modal plugin-detail">
        <div class="modal-head">
          <h3>{{ detail?.name ?? '插件详情' }}</h3>
          <button type="button" class="modal-close" @click="showDetail = false">×</button>
        </div>
        <div v-if="detailLoading" class="empty">加载中…</div>
        <div v-else-if="detail" class="modal-body">
          <div class="detail-grid">
            <div class="detail-item"><span class="label">插件 ID</span><code>{{ detail.plugin_id }}</code></div>
            <div class="detail-item"><span class="label">版本</span>{{ detail.version }}</div>
            <div class="detail-item"><span class="label">类型</span>{{ kindLabel(detail.kind) }}</div>
            <div class="detail-item">
              <span class="label">状态</span>
              <span class="state" :class="stateCls(detail.state)">{{ stateLabel(detail.state) }}</span>
            </div>
            <div class="detail-item"><span class="label">入口</span><code>{{ detail.entry || '-' }}</code></div>
            <div class="detail-item"><span class="label">最小内核</span>{{ detail.min_kernel_version || '-' }}</div>
          </div>

          <div v-if="detail.description" class="detail-block">
            <span class="label">说明</span>
            <p>{{ detail.description }}</p>
          </div>

          <div v-if="detail.permissions?.length" class="detail-block">
            <span class="label">权限声明</span>
            <div class="perm-list">
              <span v-for="p in detail.permissions" :key="permKey(p)" class="perm-tag">{{ permLabel(p) }}</span>
            </div>
          </div>

          <div v-if="detail.roles?.length" class="detail-block">
            <span class="label">推荐角色</span>
            <div class="role-list">
              <div v-for="r in detail.roles" :key="r.code" class="role-item">
                <strong>{{ r.name }}</strong>
                <code>{{ r.code }}</code>
              </div>
            </div>
          </div>

          <div v-if="detail.signature_status" class="detail-block">
            <span class="label">签名状态</span>
            <span class="state" :class="detail.signature_status === 'ok' ? 'ok' : 'warn'">
              {{ detail.signature_status === 'ok' ? '已校验' : '未校验 / 不适用' }}
            </span>
          </div>

          <div class="detail-actions">
            <button
              v-if="canInstall(detail)"
              type="button"
              class="btn"
              :disabled="acting[detail.plugin_id]"
              @click="onInstall(detail)"
            >安装并启用</button>
            <button
              v-if="canEnable(detail)"
              type="button"
              class="btn"
              :disabled="acting[detail.plugin_id]"
              @click="onEnable(detail)"
            >启用</button>
            <button
              v-if="canDisable(detail)"
              type="button"
              class="btn warn"
              :disabled="acting[detail.plugin_id]"
              @click="onDisable(detail)"
            >禁用</button>
            <button
              v-if="canUninstall(detail)"
              type="button"
              class="btn danger"
              :disabled="acting[detail.plugin_id]"
              @click="onUninstall(detail)"
            >卸载</button>
            <button type="button" class="btn ghost" @click="showDetail = false">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px 32px 40px;
}
.page-head h2 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
}
.page-head .sub {
  margin: 0 0 16px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.flash {
  margin-bottom: 12px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
}
.flash-ok {
  background: var(--color-success-light, #e8f5e9);
  color: var(--color-success, #2e7d32);
}
.flash-err {
  background: var(--color-danger-light, #fdecea);
  color: var(--color-danger, #c62828);
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.seg {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-hover);
}
.seg-btn {
  padding: 6px 14px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
}
.seg-btn.active {
  background: var(--color-bg);
  color: var(--color-primary);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}
.input {
  padding: 7px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 13px;
}
.select {
  min-width: 110px;
}
.search {
  min-width: 220px;
}
.btn {
  padding: 7px 14px;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}
.btn:hover {
  opacity: 0.88;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn.ghost {
  background: var(--color-bg);
  color: var(--color-text-secondary);
  border-color: var(--color-border);
}
.btn.mini {
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
}
.btn.warn {
  background: var(--color-warning, #f57c00);
  border-color: var(--color-warning, #f57c00);
}
.btn.danger {
  background: var(--color-danger, #c62828);
  border-color: var(--color-danger, #c62828);
}
.empty {
  padding: 48px 0;
  text-align: center;
  color: var(--color-text-muted);
  font-size: 13px;
}
.plugin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}
.plugin-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg);
}
.plugin-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.plugin-name {
  font-size: 15px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tag {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
}
.tag-primary {
  background: var(--color-primary-light);
  color: var(--color-primary);
}
.tag-info {
  background: var(--color-info-light, #e3f2fd);
  color: var(--color-info, #1565c0);
}
.plugin-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--color-text-muted);
  font-size: 12px;
}
.plugin-meta code {
  font-size: 11px;
}
.plugin-perms {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-height: 18px;
}
.perm-tag {
  padding: 2px 7px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-hover);
  color: var(--color-text-secondary);
  font-size: 11px;
}
.perm-more {
  padding: 2px 6px;
  color: var(--color-text-muted);
  font-size: 11px;
}
.plugin-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid var(--color-border-light);
}
.state {
  font-size: 12px;
  font-weight: 600;
}
.state.ok {
  color: var(--color-success, #2e7d32);
}
.state.warn {
  color: var(--color-warning, #f57c00);
}
.state.info {
  color: var(--color-info, #1565c0);
}
.state.muted {
  color: var(--color-text-muted);
}
.actions {
  display: flex;
  gap: 6px;
}
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 16px;
}
.pager-info {
  color: var(--color-text-secondary);
  font-size: 13px;
}
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.4);
}
.modal {
  width: min(640px, 100%);
  max-height: 86vh;
  overflow-y: auto;
  border-radius: var(--radius-md);
  background: var(--color-bg);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border-light);
}
.modal-head h3 {
  margin: 0;
  font-size: 16px;
}
.modal-close {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--color-text-muted);
  cursor: pointer;
}
.modal-body {
  padding: 20px;
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-hover);
  font-size: 13px;
}
.detail-item .label,
.detail-block .label {
  color: var(--color-text-muted);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.detail-item code {
  font-size: 12px;
  word-break: break-all;
}
.detail-block {
  margin-top: 14px;
}
.detail-block p {
  margin: 6px 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.perm-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.role-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 6px;
}
.role-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-hover);
  font-size: 13px;
}
.role-item code {
  font-size: 12px;
}
.detail-actions {
  display: flex;
  gap: 8px;
  margin-top: 20px;
  flex-wrap: wrap;
}
</style>
