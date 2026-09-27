<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  activateEndpoint,
  applyEndpoint,
  createEndpoint,
  deleteEndpoint,
  fetchEndpoints,
  fetchHardware,
  fetchOverview,
  fetchRecommend,
  syncEndpointEnv,
  testEndpoint,
  testSavedEndpoint,
  updateEndpoint,
  type EndpointItem,
  type HardwarePayload,
  type OverviewOut,
  type Recommendation,
  type RuntimeSnapshot,
  type TestResult,
} from '@/api/model'

const overview = ref<OverviewOut | null>(null)
const hardware = ref<HardwarePayload | null>(null)
const recommendation = ref<Recommendation | null>(null)
const endpoints = ref<EndpointItem[]>([])
const runtime = ref<RuntimeSnapshot | null>(null)

const loading = reactive({ overview: false, hardware: false, recommend: false, endpoints: false })
const refreshing = ref(false)
const msg = reactive({ type: '', text: '' })

const testResult = ref<TestResult | null>(null)
const applying = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)

const KINDS = [
  { key: 'local_ollama', label: '本地 Ollama' },
  { key: 'cloud_openai', label: '云端 OpenAI 兼容' },
]

const emptyForm = () => ({
  name: '',
  kind: 'local_ollama',
  base_url: 'http://127.0.0.1:11434',
  model: '',
  api_key: '',
  param_scale: '',
  remark: '',
  enabled: true,
})
const form = reactive(emptyForm())

const runtimeTag = computed(() => {
  if (!runtime.value) return { label: '未知', cls: 'muted' }
  if (!runtime.value.ai_enabled) return { label: 'AI 未启用', cls: 'muted' }
  return runtime.value.ai_ready
    ? { label: 'AI 就绪', cls: 'ok' }
    : { label: 'AI 已启用·未就绪', cls: 'warn' }
})

const hasGpu = computed(() => (hardware.value?.gpus?.length ?? 0) > 0)

function tip(type: string, text: string) {
  msg.type = type
  msg.text = text
}

function errText(e: any): string {
  return e?.response?.data?.message || e?.message || '请求失败'
}

function mb(v?: number | null) {
  if (v === null || v === undefined) return '-'
  return v >= 1024 ? `${(v / 1024).toFixed(1)} GB` : `${v} MB`
}

function gb(v?: number | null) {
  return v === null || v === undefined ? '-' : `${Number(v).toFixed(1)} GB`
}

function pct(v?: number | null) {
  return v === null || v === undefined ? '-' : `${Number(v).toFixed(1)}%`
}

function dt(v?: string | null) {
  return v ? String(v).replace('T', ' ').slice(0, 19) : '-'
}

async function loadOverview() {
  loading.overview = true
  try {
    const res = await fetchOverview()
    overview.value = res.data
    runtime.value = res.data?.runtime ?? null
  } catch (e) {
    tip('error', `概览加载失败：${errText(e)}`)
  } finally {
    loading.overview = false
  }
}

async function loadHardware(refresh = false) {
  loading.hardware = true
  if (refresh) refreshing.value = true
  try {
    const res = await fetchHardware(refresh)
    hardware.value = res.data
    if (res.data?.recommendation) recommendation.value = res.data.recommendation
  } catch (e) {
    tip('error', `硬件探测失败：${errText(e)}`)
  } finally {
    loading.hardware = false
    refreshing.value = false
  }
}

async function loadRecommend() {
  loading.recommend = true
  try {
    const res = await fetchRecommend(false)
    recommendation.value = res.data?.recommendation ?? recommendation.value
  } catch (e) {
    tip('error', `模型推荐失败：${errText(e)}`)
  } finally {
    loading.recommend = false
  }
}

async function loadEndpoints() {
  loading.endpoints = true
  try {
    const res = await fetchEndpoints()
    endpoints.value = res.data?.items ?? []
    runtime.value = res.data?.runtime ?? runtime.value
  } catch (e) {
    tip('error', `端点列表加载失败：${errText(e)}`)
  } finally {
    loading.endpoints = false
  }
}

function fillPreset(p: { key: string; label: string; base_url: string; model: string }) {
  form.kind = 'cloud_openai'
  form.base_url = p.base_url
  form.model = p.model
  if (!form.name) form.name = p.label
}

function resetForm() {
  Object.assign(form, emptyForm())
  editingId.value = null
}

function startEdit(row: EndpointItem) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    kind: row.kind,
    base_url: row.base_url,
    model: row.model,
    api_key: '',
    param_scale: row.param_scale ?? '',
    remark: row.remark ?? '',
    enabled: row.enabled,
  })
}

async function submitForm() {
  if (!form.name.trim() || !form.base_url.trim() || !form.model.trim()) {
    tip('error', '名称、Base URL、模型名均为必填项')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      kind: form.kind,
      base_url: form.base_url.trim(),
      model: form.model.trim(),
      api_key: form.api_key ? form.api_key : undefined,
      param_scale: form.param_scale || undefined,
      enabled: form.enabled,
    }
    if (editingId.value) {
      await updateEndpoint(editingId.value, payload)
      tip('ok', '端点已更新')
    } else {
      await createEndpoint(payload)
      tip('ok', '端点已新增')
    }
    resetForm()
    await Promise.all([loadEndpoints(), loadOverview()])
  } catch (e) {
    tip('error', `保存失败：${errText(e)}`)
  } finally {
    saving.value = false
  }
}

async function runTest(row?: EndpointItem) {
  try {
    testResult.value = null
    const res = row
      ? await testSavedEndpoint(row.id)
      : await testEndpoint({
          kind: form.kind,
          base_url: form.base_url,
          model: form.model,
          api_key: form.api_key || undefined,
        })
    testResult.value = res.data
    tip(res.data?.ok ? 'ok' : 'warn', res.data?.message || (res.data?.ok ? '自检通过' : '自检未通过'))
    if (row) await loadEndpoints()
  } catch (e) {
    tip('error', `自检失败：${errText(e)}`)
  }
}

async function activate(row: EndpointItem) {
  try {
    await activateEndpoint(row.id)
    tip('ok', `已将「${row.name}」设为当前生效端点`)
    await Promise.all([loadEndpoints(), loadOverview()])
  } catch (e) {
    tip('error', `激活失败：${errText(e)}`)
  }
}

async function syncEnv(row: EndpointItem) {
  try {
    const res = await syncEndpointEnv(row.id, true)
    const data = res.data as any
    tip('ok', data?.message || `已回写运行配置：${row.name}`)
    await Promise.all([loadEndpoints(), loadOverview()])
  } catch (e) {
    tip('error', `回写失败：${errText(e)}`)
  }
}

async function removeEndpoint(row: EndpointItem) {
  if (!window.confirm(`确认删除端点「${row.name}」？该操作不可撤销。`)) return
  try {
    await deleteEndpoint(row.id)
    tip('ok', '端点已删除')
    await Promise.all([loadEndpoints(), loadOverview()])
  } catch (e) {
    tip('error', `删除失败：${errText(e)}`)
  }
}

async function applyRecommended(mode: 'local' | 'cloud', model?: string, baseUrl?: string) {
  applying.value = true
  try {
    const res = await applyEndpoint({
      mode,
      name: mode === 'local' ? `本地 - ${model || 'Ollama'}` : `云端 - ${model || 'OpenAI 兼容'}`,
      base_url: baseUrl,
      model,
      verify: true,
      activate: true,
    })
    const test = res.data?.test
    tip(test?.ok === false ? 'warn' : 'ok', test?.message || '一键接入已完成')
    await Promise.all([loadEndpoints(), loadOverview()])
  } catch (e) {
    tip('error', `一键接入失败：${errText(e)}`)
  } finally {
    applying.value = false
  }
}

function loadAll() {
  loadOverview()
  loadHardware(false)
  loadRecommend()
  loadEndpoints()
}

onMounted(loadAll)
</script>

<template>
  <div class="model-center">
    <div class="page-head">
      <div>
        <h2>模型中心</h2>
        <p class="sub">本机硬件探测 · 模型自动适配推荐 · 本地 Ollama / 云端 OpenAI 兼容端点接入</p>
      </div>
      <div class="head-actions">
        <span class="tag" :class="runtimeTag.cls">{{ runtimeTag.label }}</span>
        <button class="btn" :disabled="refreshing" @click="loadHardware(true)">
          {{ refreshing ? '探测中…' : '重新探测硬件' }}
        </button>
        <button class="btn" @click="loadAll">刷新全部</button>
      </div>
    </div>

    <p v-if="msg.text" class="msg" :class="msg.type">{{ msg.text }}</p>

    <div class="panel runtime-panel">
      <div class="panel-title">运行配置</div>
      <div class="kv-grid">
        <div class="kv"><span>AI 模式</span><b>{{ runtime?.ai_mode || '-' }}</b></div>
        <div class="kv"><span>Base URL</span><b class="mono">{{ runtime?.base_url || '-' }}</b></div>
        <div class="kv"><span>当前模型</span><b class="mono">{{ runtime?.model || '-' }}</b></div>
        <div class="kv">
          <span>密钥</span>
          <b>{{ runtime?.api_key_configured ? (runtime?.api_key_hint || '已配置') : '未配置' }}</b>
        </div>
        <div class="kv"><span>.env 路径</span><b class="mono">{{ overview?.env_path || '-' }}</b></div>
      </div>
      <div v-if="overview" class="stat-row">
        <div class="stat"><em>{{ overview.stats.total }}</em><span>端点总数</span></div>
        <div class="stat"><em>{{ overview.stats.enabled }}</em><span>已启用</span></div>
        <div class="stat"><em>{{ overview.stats.local }}</em><span>本地</span></div>
        <div class="stat"><em>{{ overview.stats.cloud }}</em><span>云端</span></div>
        <div class="stat"><em>{{ overview.stats.tested }}</em><span>已自检</span></div>
        <div class="stat"><em>{{ overview.stats.test_ok }}</em><span>自检通过</span></div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">
        硬件探测
        <small v-if="hardware">
          {{ hardware.host_snapshot?.available ? '宿主机探测' : '容器内探测' }} ·
          {{ dt(hardware.probed_at) }}
          <template v-if="hardware.probe_ms"> · {{ hardware.probe_ms }} ms</template>
        </small>
      </div>
      <div v-if="loading.hardware && !hardware" class="empty">探测中…</div>
      <template v-else-if="hardware">
        <div class="hw-grid">
          <div class="hw-card">
            <div class="hw-label">CPU</div>
            <div class="hw-main mono">{{ hardware.cpu?.model || '-' }}</div>
            <div class="hw-sub">
              物理核 {{ hardware.cpu?.physical_cores ?? '-' }} · 逻辑核
              {{ hardware.cpu?.logical_cores ?? '-' }} · 主频
              {{ hardware.cpu?.freq_mhz ? hardware.cpu.freq_mhz + ' MHz' : '-' }}
            </div>
            <div class="hw-sub">来源：{{ hardware.cpu?.source || '-' }}</div>
          </div>
          <div class="hw-card">
            <div class="hw-label">内存</div>
            <div class="hw-main">{{ mb(hardware.memory?.total_mb) }}</div>
            <div class="hw-sub">
              可用 {{ mb(hardware.memory?.available_mb) }} · 占用
              {{ pct(hardware.memory?.used_percent) }}
            </div>
            <div class="hw-bar">
              <i :style="{ width: Math.min(hardware.memory?.used_percent ?? 0, 100) + '%' }"></i>
            </div>
          </div>
          <div class="hw-card">
            <div class="hw-label">GPU 显存合计</div>
            <div class="hw-main">{{ gb(hardware.gpu_vram?.total_gb) }}</div>
            <div class="hw-sub">
              {{ hasGpu ? `${hardware.gpus?.length} 张 GPU` : '未检测到 GPU' }} · 显存数值
              {{ hardware.gpu_vram?.accurate ? '准确' : '估算' }}
            </div>
            <div class="hw-sub">厂商：{{ hardware.gpu_vram?.vendors?.join('、') || '-' }}</div>
          </div>
          <div class="hw-card">
            <div class="hw-label">网络出口</div>
            <div class="hw-main mono">{{ hardware.network?.egress_ip || '-' }}</div>
            <div class="hw-sub">
              主机 {{ hardware.network?.hostname || '-' }} · DNS
              {{ hardware.network?.dns_ok ? '正常' : '异常' }} · TCP
              {{ hardware.network?.tcp_ok ? '正常' : '异常' }}
            </div>
          </div>
        </div>

        <div v-if="hardware.gpus?.length" class="sub-block">
          <div class="sub-title">GPU 明细</div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>名称</th><th>厂商</th><th>显存总计</th><th>显存可用</th>
                  <th>驱动</th><th>来源</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(g, i) in hardware.gpus" :key="i">
                  <td class="mono">{{ g.name || '-' }}</td>
                  <td>{{ g.vendor || '-' }}</td>
                  <td>{{ mb(g.vram_total_mb) }}</td>
                  <td>{{ mb(g.vram_free_mb) }}</td>
                  <td>{{ g.driver || '-' }}</td>
                  <td>{{ g.source || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="hardware.disks?.length" class="sub-block">
          <div class="sub-title">磁盘</div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr><th>挂载点</th><th>总量</th><th>可用</th><th>占用</th><th>来源</th></tr>
              </thead>
              <tbody>
                <tr v-for="(d, i) in hardware.disks" :key="i">
                  <td class="mono">{{ d.mount || '-' }}</td>
                  <td>{{ gb(d.total_gb) }}</td>
                  <td>{{ gb(d.free_gb) }}</td>
                  <td>{{ pct(d.used_percent) }}</td>
                  <td>{{ d.source || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="hardware.network?.targets?.length" class="sub-block">
          <div class="sub-title">网络可达性</div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr><th>目标</th><th>地址</th><th>状态</th><th>时延</th><th>说明</th></tr>
              </thead>
              <tbody>
                <tr v-for="(t, i) in hardware.network.targets" :key="i">
                  <td>{{ t.label }}</td>
                  <td class="mono">{{ t.url || t.host || '-' }}</td>
                  <td><span class="tag" :class="t.reachable ? 'ok' : 'warn'">{{ t.reachable ? '可达' : '不可达' }}</span></td>
                  <td>{{ t.latency_ms != null ? t.latency_ms + ' ms' : '-' }}</td>
                  <td>{{ t.message || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="hardware.degradations?.length" class="sub-block">
          <div class="sub-title">探测降级说明</div>
          <ul class="deg-list">
            <li v-for="(d, i) in hardware.degradations" :key="i">
              <b>{{ d.item }}</b>：{{ d.reason }}
              <span v-if="d.suggestion">（建议：{{ d.suggestion }}）</span>
            </li>
          </ul>
        </div>
      </template>
    </div>

    <div class="panel">
      <div class="panel-title">
        模型推荐
        <small v-if="recommendation">生成于 {{ dt(recommendation.generated_at) }}</small>
      </div>
      <div v-if="!recommendation" class="empty">推荐生成中…</div>
      <template v-else>
        <div class="rec-head">
          <span class="tag" :class="recommendation.tier?.uncertain ? 'warn' : 'ok'">
            {{ recommendation.tier?.label || '档位未知' }}
          </span>
          <span v-if="recommendation.hardware_summary" class="rec-sum">
            显存 {{ gb(recommendation.hardware_summary.vram_total_gb) }} ·
            内存 {{ gb(recommendation.hardware_summary.ram_total_gb) }} ·
            CPU {{ recommendation.hardware_summary.cpu_cores ?? '-' }} 核 ·
            GPU {{ recommendation.hardware_summary.gpu_count ?? 0 }} 张
          </span>
        </div>
        <p class="rationale">{{ recommendation.rationale || '-' }}</p>

        <div v-if="recommendation.primary" class="primary-card">
          <div>
            <div class="pc-title">{{ recommendation.primary.display }}</div>
            <div class="pc-sub">
              参数量 {{ recommendation.primary.params }} · 量化
              {{ recommendation.primary.quant }} · 需显存
              {{ gb(recommendation.primary.vram_required_gb) }}
            </div>
            <div class="pc-sub">
              适配：{{ recommendation.primary.fit || '-' }}
              <span v-if="recommendation.primary.note"> · {{ recommendation.primary.note }}</span>
            </div>
          </div>
          <button
            class="btn primary"
            :disabled="applying"
            @click="applyRecommended('local', recommendation.primary.local?.model || recommendation.primary.key)"
          >
            一键接入为本地端点
          </button>
        </div>

        <div v-if="recommendation.items?.length" class="sub-block">
          <div class="sub-title">候选模型</div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>模型</th><th>参数量</th><th>量化</th><th>需显存</th>
                  <th>需内存</th><th>适配</th><th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in recommendation.items" :key="m.key">
                  <td>{{ m.display }}</td>
                  <td>{{ m.params }}</td>
                  <td>{{ m.quant }}</td>
                  <td>{{ gb(m.vram_required_gb) }}</td>
                  <td>{{ m.ram_required_gb != null ? gb(m.ram_required_gb) : '-' }}</td>
                  <td>
                    <span class="tag" :class="m.fit === 'ok' ? 'ok' : m.fit === 'risk' ? 'warn' : 'muted'">
                      {{ m.fit === 'ok' ? '可运行' : m.fit === 'risk' ? '临界' : m.fit === 'over' ? '超限' : (m.fit || '-') }}
                    </span>
                  </td>
                  <td>
                    <button class="btn mini" :disabled="applying" @click="applyRecommended('local', m.local?.model || m.key)">
                      接入
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="recommendation.cloud?.presets?.length" class="sub-block">
          <div class="sub-title">
            云端预置
            <small v-if="recommendation.cloud?.recommended">（本机算力有限，建议使用云端）</small>
          </div>
          <div class="preset-row">
            <button
              v-for="p in recommendation.cloud.presets"
              :key="p.key"
              class="chip"
              @click="fillPreset(p)"
            >
              {{ p.label }}
            </button>
          </div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr><th>预置</th><th>Base URL</th><th>模型</th><th>规模</th><th>操作</th></tr>
              </thead>
              <tbody>
                <tr v-for="p in recommendation.cloud.presets" :key="p.key">
                  <td>{{ p.label }}</td>
                  <td class="mono">{{ p.base_url }}</td>
                  <td class="mono">{{ p.model }}</td>
                  <td>{{ p.scale || '-' }}</td>
                  <td>
                    <button class="btn mini" @click="fillPreset(p)">填入表单</button>
                    <button
                      class="btn mini"
                      :disabled="applying"
                      @click="applyRecommended('cloud', p.model, p.base_url)"
                    >
                      一键接入
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="recommendation.degradations?.length" class="sub-block">
          <div class="sub-title">推荐降级说明</div>
          <ul class="deg-list">
            <li v-for="(d, i) in recommendation.degradations" :key="i">
              <b>{{ d.item }}</b>：{{ d.reason }}
              <span v-if="d.suggestion">（建议：{{ d.suggestion }}）</span>
            </li>
          </ul>
        </div>
      </template>
    </div>

    <div class="panel">
      <div class="panel-title">{{ editingId ? `编辑端点 #${editingId}` : '新增接入端点' }}</div>
      <div class="form">
        <label>
          <span>名称</span>
          <input v-model.trim="form.name" placeholder="如：本地 Ollama / DeepSeek 云" />
        </label>
        <label>
          <span>类型</span>
          <select v-model="form.kind">
            <option v-for="k in KINDS" :key="k.key" :value="k.key">{{ k.label }}</option>
          </select>
        </label>
        <label>
          <span>Base URL</span>
          <input v-model.trim="form.base_url" placeholder="http://127.0.0.1:11434 或 https://api.deepseek.com/v1" />
        </label>
        <label>
          <span>模型名</span>
          <input v-model.trim="form.model" placeholder="如：qwen2.5:7b / deepseek-chat" />
        </label>
        <label>
          <span>API Key</span>
          <input
            v-model.trim="form.api_key"
            type="password"
            :placeholder="editingId ? '留空表示不修改' : '本地 Ollama 可留空'"
          />
        </label>
        <label>
          <span>规模标注</span>
          <input v-model.trim="form.param_scale" placeholder="可选，如 7B" />
        </label>
        <label>
          <span>备注</span>
          <input v-model.trim="form.remark" placeholder="可选" />
        </label>
        <label class="check">
          <input v-model="form.enabled" type="checkbox" />
          <span>启用该端点</span>
        </label>
        <div class="form-actions">
          <button class="btn primary" :disabled="saving" @click="submitForm">
            {{ saving ? '保存中…' : editingId ? '保存修改' : '新增端点' }}
          </button>
          <button class="btn" @click="runTest()">连通性自检（当前表单）</button>
          <button class="btn" @click="resetForm">重置</button>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">接入端点</div>
      <div v-if="loading.endpoints && !endpoints.length" class="empty">加载中…</div>
      <div v-else-if="!endpoints.length" class="empty">暂无端点，请通过上方表单或模型推荐一键接入</div>
      <div v-else class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th><th>名称</th><th>类型</th><th>Base URL</th><th>模型</th>
              <th>密钥</th><th>启用</th><th>生效</th><th>最近自检</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in endpoints" :key="row.id" :class="{ 'row-active': row.is_active || row.is_effective }">
              <td>{{ row.id }}</td>
              <td>{{ row.name }}</td>
              <td>{{ row.kind_label || row.kind }}</td>
              <td class="mono">{{ row.base_url }}</td>
              <td class="mono">{{ row.model }}</td>
              <td>{{ row.has_api_key ? (row.api_key_hint || '已配置') : '-' }}</td>
              <td>
                <span class="tag" :class="row.enabled ? 'ok' : 'muted'">{{ row.enabled ? '启用' : '停用' }}</span>
              </td>
              <td>
                <span class="tag" :class="row.is_active || row.is_effective ? 'ok' : 'muted'">
                  {{ row.is_active || row.is_effective ? '生效中' : '未生效' }}
                </span>
              </td>
              <td>
                <template v-if="row.last_test_at">
                  <span class="tag" :class="row.last_test_ok ? 'ok' : 'warn'">{{ row.last_test_ok ? '通过' : '未通过' }}</span>
                  <div class="muted small">
                    {{ dt(row.last_test_at) }}
                    <template v-if="row.last_test_latency_ms != null"> · {{ row.last_test_latency_ms }} ms</template>
                  </div>
                </template>
                <span v-else class="muted">未自检</span>
              </td>
              <td class="ops">
                <button class="btn mini" @click="runTest(row)">自检</button>
                <button class="btn mini" :disabled="row.is_active || row.is_effective" @click="activate(row)">激活</button>
                <button class="btn mini" @click="syncEnv(row)">回写 .env</button>
                <button class="btn mini" @click="startEdit(row)">编辑</button>
                <button class="btn mini danger" @click="removeEndpoint(row)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="testResult" class="panel">
      <div class="panel-title">
        连通性自检结果
        <small>{{ dt(testResult.tested_at) }}</small>
      </div>
      <div class="test-head">
        <span class="tag" :class="testResult.ok ? 'ok' : 'warn'">{{ testResult.ok ? '通过' : '未通过' }}</span>
        <span class="rec-sum">
          {{ testResult.message || '-' }}
          <template v-if="testResult.latency_ms != null"> · 时延 {{ testResult.latency_ms }} ms</template>
        </span>
      </div>
      <div class="kv-grid">
        <div class="kv"><span>类型</span><b>{{ testResult.kind || '-' }}</b></div>
        <div class="kv"><span>检测地址</span><b class="mono">{{ testResult.checked_url || '-' }}</b></div>
        <div class="kv"><span>模型</span><b class="mono">{{ testResult.model || '-' }}</b></div>
        <div class="kv">
          <span>模型可用</span>
          <b>{{ testResult.model_available == null ? '-' : testResult.model_available ? '可用' : '不可用' }}</b>
        </div>
        <div class="kv"><span>版本</span><b>{{ testResult.version || '-' }}</b></div>
        <div class="kv">
          <span>端点</span>
          <b>{{ testResult.endpoint_name || testResult.endpoint_id || '-' }}</b>
        </div>
        <div v-if="testResult.suggested_base_url" class="kv">
          <span>建议地址</span><b class="mono">{{ testResult.suggested_base_url }}</b>
        </div>
      </div>
      <div v-if="testResult.models?.length" class="sub-block">
        <div class="sub-title">可用模型（{{ testResult.models.length }}）</div>
        <div class="model-tags">
          <span v-for="m in testResult.models" :key="m" class="chip">{{ m }}</span>
        </div>
      </div>
      <div v-if="testResult.steps?.length" class="sub-block">
        <div class="sub-title">检测步骤</div>
        <ul class="step-list">
          <li v-for="(s, i) in testResult.steps" :key="i">
            <span class="tag" :class="s.ok ? 'ok' : 'warn'">{{ s.ok ? '✓' : '✗' }}</span>
            <b>{{ s.step }}</b>
            <span v-if="s.detail" class="muted"> — {{ s.detail }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.model-center {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 32px;
  max-width: 1400px;
  margin: 0 auto;
}
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.page-head h2 {
  margin: 0 0 4px;
  font-size: 20px;
  color: var(--color-text-primary, #1f2329);
}
.page-head .sub {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary, #646a73);
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.msg {
  margin: 0;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  border-left: 3px solid var(--color-border, #dcdfe6);
  background: var(--color-bg-sub, #f7f8fa);
}
.msg.ok {
  border-left-color: #34c724;
  color: #1f7a1f;
}
.msg.warn {
  border-left-color: #ff8800;
  color: #a35b00;
}
.msg.error {
  border-left-color: #f54a45;
  color: #b3261e;
}
.runtime-panel .kv-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px 16px;
}
.kv {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
  min-width: 0;
}
.kv span {
  color: var(--color-text-secondary, #646a73);
  flex: 0 0 auto;
}
.kv b {
  font-weight: 500;
  color: var(--color-text-primary, #1f2329);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mono {
  font-family: 'JetBrains Mono', Consolas, Menlo, monospace;
}
.stat-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.stat {
  flex: 1 1 90px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--color-bg-sub, #f7f8fa);
  text-align: center;
}
.stat em {
  display: block;
  font-style: normal;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-primary, #3370ff);
}
.stat span {
  font-size: 12px;
  color: var(--color-text-secondary, #646a73);
}
.panel-title small {
  margin-left: 8px;
  font-weight: 400;
  font-size: 12px;
  color: var(--color-text-secondary, #646a73);
}
.hw-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}
.hw-card {
  padding: 10px 12px;
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 8px;
}
.hw-label {
  font-size: 12px;
  color: var(--color-text-secondary, #646a73);
  margin-bottom: 4px;
}
.hw-main {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary, #1f2329);
  word-break: break-all;
}
.hw-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary, #646a73);
}
.hw-bar {
  margin-top: 6px;
  height: 6px;
  border-radius: 3px;
  background: var(--color-bg-sub, #f0f1f3);
  overflow: hidden;
}
.hw-bar i {
  display: block;
  height: 100%;
  background: var(--color-primary, #3370ff);
}
.sub-block {
  margin-top: 14px;
}
.sub-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--color-text-primary, #1f2329);
}
.deg-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--color-text-secondary, #646a73);
  line-height: 1.8;
}
.rec-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.rec-sum {
  font-size: 12px;
  color: var(--color-text-secondary, #646a73);
}
.rationale {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--color-text-primary, #1f2329);
  line-height: 1.6;
}
.primary-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
  padding: 12px;
  border: 1px solid var(--color-primary, #3370ff);
  border-radius: 8px;
  background: rgba(51, 112, 255, 0.05);
  flex-wrap: wrap;
}
.pc-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary, #1f2329);
}
.pc-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary, #646a73);
}
.preset-row,
.model-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.chip {
  padding: 3px 10px;
  border-radius: 12px;
  border: 1px solid var(--color-border, #dcdfe6);
  background: var(--color-bg-sub, #f7f8fa);
  font-size: 12px;
  cursor: pointer;
  color: var(--color-text-primary, #1f2329);
}
.chip:hover {
  border-color: var(--color-primary, #3370ff);
  color: var(--color-primary, #3370ff);
}
.table-scroll {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-border, #e5e6eb);
  text-align: left;
  vertical-align: middle;
  white-space: nowrap;
}
th {
  font-weight: 600;
  color: var(--color-text-secondary, #646a73);
  background: var(--color-bg-sub, #f7f8fa);
}
tr.row-active td {
  background: rgba(52, 199, 36, 0.06);
}
td.ops {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.muted {
  color: var(--color-text-secondary, #86909c);
}
.small {
  font-size: 11px;
}
.empty {
  padding: 18px 0;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-secondary, #86909c);
}
.form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 10px 16px;
  align-items: center;
}
.form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-secondary, #646a73);
}
.form label.check {
  flex-direction: row;
  align-items: center;
  gap: 6px;
}
.form input,
.form select {
  padding: 6px 8px;
  border: 1px solid var(--color-border, #dcdfe6);
  border-radius: 6px;
  font-size: 13px;
  background: var(--color-bg, #fff);
  color: var(--color-text-primary, #1f2329);
}
.form-actions {
  grid-column: 1 / -1;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.btn {
  padding: 5px 12px;
  border: 1px solid var(--color-border, #dcdfe6);
  border-radius: 6px;
  background: var(--color-bg, #fff);
  color: var(--color-text-primary, #1f2329);
  font-size: 13px;
  cursor: pointer;
}
.btn:hover:not(:disabled) {
  border-color: var(--color-primary, #3370ff);
  color: var(--color-primary, #3370ff);
}
.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.btn.primary {
  background: var(--color-primary, #3370ff);
  border-color: var(--color-primary, #3370ff);
  color: #fff;
}
.btn.primary:hover:not(:disabled) {
  opacity: 0.9;
  color: #fff;
}
.btn.mini {
  padding: 3px 8px;
  font-size: 12px;
}
.btn.danger {
  color: #f54a45;
  border-color: rgba(245, 74, 69, 0.4);
}
.btn.danger:hover:not(:disabled) {
  background: #f54a45;
  color: #fff;
  border-color: #f54a45;
}
.tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
  background: var(--color-bg-sub, #f0f1f3);
  color: var(--color-text-secondary, #646a73);
}
.tag.ok {
  background: rgba(52, 199, 36, 0.12);
  color: #1f7a1f;
}
.tag.warn {
  background: rgba(255, 136, 0, 0.12);
  color: #a35b00;
}
.tag.muted {
  background: var(--color-bg-sub, #f0f1f3);
  color: #86909c;
}
.test-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.step-list {
  margin: 0;
  padding-left: 0;
  list-style: none;
  font-size: 12px;
  line-height: 1.9;
  color: var(--color-text-primary, #1f2329);
}
.step-list li {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ===== 响应式自适应（窗口缩放） ===== */
@media (max-width: 1024px) {
  .model-center {
    padding: 20px 16px;
  }
}
@media (max-width: 768px) {
  .model-center {
    padding: 16px 12px;
  }
}
@media (max-width: 480px) {
  .model-center {
    padding: 12px 10px;
  }
}
</style>
