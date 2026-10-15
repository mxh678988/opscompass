<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  createPredictionRun,
  fetchPredictionRun,
  fetchPredictionRuns,
  type PredictionJob,
  type PredictionResultItem,
  type PredictionRunIn,
} from '@/api/predictive'
import {
  createAudienceSegment,
  fetchAudienceSegments,
  patchAudienceSegment,
  reuseAudienceSegment,
  type AudienceSegment,
} from '@/api/audience'
import {
  createKnowledgeDoc,
  deleteKnowledgeDoc,
  fetchKnowledgeDocs,
  searchKnowledgeDocs,
  type KnowledgeDoc,
} from '@/api/knowledge'
import {
  analyzeAgentRun,
  completeAgentRun,
  createAgentRun,
  fetchAgentRun,
  fetchAgentRuns,
  patchAgentRun,
  type AgentRun,
} from '@/api/agent'

const tab = ref<'prediction' | 'audience' | 'knowledge' | 'agent'>('prediction')
function switchTab(t: 'prediction' | 'audience' | 'knowledge' | 'agent') {
  tab.value = t
}
const msg = reactive({ type: '', text: '' })
let msgTimer: number | undefined
function tip(type: 'ok' | 'warn' | 'error', text: string) {
  msg.type = type
  msg.text = text
  if (msgTimer) window.clearTimeout(msgTimer)
  msgTimer = window.setTimeout(() => { msg.text = '' }, 6000)
}
function errText(e: any): string {
  return e?.response?.data?.message || e?.message || '请求失败'
}
function dt(v?: string | null) {
  return v ? String(v).replace('T', ' ').slice(0, 19) : '-'
}
function pct(v?: number | null) {
  return v === null || v === undefined ? '-' : `${(v * 100).toFixed(1)}%`
}

/* ---------- 状态识别 ---------- */
const STATUS_CLS: Record<string, string> = {
  running: 'ok', pending: 'muted', done: 'ok', executing: 'ok',
  awaiting_approval: 'warn', analyzing: 'warn', draft: 'muted', ready: 'ok',
  active: 'ok', expired: 'muted', failed: 'error', rejected: 'error', archived: 'muted',
}
const STATUS_LABEL: Record<string, string> = {
  running: '运行中', pending: '待处理', done: '已完成', executing: '执行中',
  awaiting_approval: '待审批', analyzing: '分析中', draft: '草稿', ready: '就绪',
  active: '生效中', expired: '已过期', failed: '失败', rejected: '已驳回', archived: '已归档',
  published: '已发布', high: '高概率', medium: '中概率', low: '低概率',
}
function stLabel(v?: string | null) {
  return v ? (STATUS_LABEL[v] ?? v) : '-'
}
function stCls(v?: string | null) {
  return v ? (STATUS_CLS[v] ?? 'muted') : 'muted'
}

/* ---------- 预测任务 ---------- */
const runs = ref<PredictionJob[]>([])
const runsLoading = ref(false)
const predForm = reactive<PredictionRunIn>({
  name: '',
  target: 'churn',
  mode: 'local',
  threshold: 0.5,
  rule_fallback: true,
  subject_keys: [],
})
const predKeysText = ref('')
const predSubmitting = ref(false)
const predDetail = ref<PredictionJob | null>(null)
const predDetailLoading = ref(false)

async function loadRuns() {
  runsLoading.value = true
  try {
    const res = await fetchPredictionRuns({ page: 1, size: 100 })
    runs.value = res.data?.items ?? []
  } catch (e) {
    tip('error', `预测任务加载失败：${errText(e)}`)
  } finally {
    runsLoading.value = false
  }
}

async function submitPrediction() {
  if (!predForm.name.trim()) {
    tip('warn', '请先填写任务名称')
    return
  }
  if (predForm.threshold == null || predForm.threshold < 0 || predForm.threshold > 1) {
    tip('warn', '判定阈值需在 0~1 之间')
    return
  }
  predSubmitting.value = true
  try {
    predForm.subject_keys = predKeysText.value
      .split(/[,，\n]/)
      .map((s) => s.trim())
      .filter(Boolean)
    const res = await createPredictionRun({ ...predForm })
    tip('ok', `预测任务「${res.data?.name ?? ''}」已发起`)
    predForm.name = ''
    predKeysText.value = ''
    await loadRuns()
  } catch (e) {
    tip('error', `预测发起失败：${errText(e)}`)
  } finally {
    predSubmitting.value = false
  }
}

async function openPredDetail(job: PredictionJob) {
  predDetailLoading.value = true
  predDetail.value = job
  try {
    const res = await fetchPredictionRun(job.id)
    predDetail.value = res.data
  } catch (e) {
    tip('error', `预测详情加载失败：${errText(e)}`)
  } finally {
    predDetailLoading.value = false
  }
}

function bandCount(results: PredictionResultItem[] | undefined, band: string) {
  return (results ?? []).filter((r) => r.band === band).length
}

/* ---------- 人群包 ---------- */
const segments = ref<AudienceSegment[]>([])
const segLoading = ref(false)
const segForm = reactive({
  name: '',
  target: 'churn' as 'churn' | 'conversion',
  source_job_id: null as number | null,
  min_prob: 0.6,
  max_prob: null as number | null,
  band: 'high' as 'high' | 'medium' | 'low' | '',
  description: '',
})
const segSubmitting = ref(false)
const reuseForm = reactive({
  name: '',
  source_segment_id: null as number | null,
  min_prob: 0.5,
  max_prob: null as number | null,
  band: '' as 'high' | 'medium' | 'low' | '',
  description: '',
})
const reuseSubmitting = ref(false)
const showReuse = ref(false)
const segmentDetail = ref<AudienceSegment | null>(null)

async function loadSegments() {
  segLoading.value = true
  try {
    const res = await fetchAudienceSegments({ page: 1, size: 100 })
    segments.value = res.data?.items ?? []
  } catch (e) {
    tip('error', `人群包加载失败：${errText(e)}`)
  } finally {
    segLoading.value = false
  }
}

async function submitSegment() {
  if (!segForm.name.trim()) {
    tip('warn', '请先填写人群包名称')
    return
  }
  if (segForm.min_prob < 0 || segForm.min_prob > 1 || (segForm.max_prob !== null && (segForm.max_prob < 0 || segForm.max_prob > 1 || segForm.max_prob < segForm.min_prob))) {
    tip('warn', '概率区间不合法：需在 0~1 之间且最小值不大于最大值')
    return
  }
  segSubmitting.value = true
  try {
    await createAudienceSegment({
      name: segForm.name,
      target: segForm.target,
      source_job_id: segForm.source_job_id,
      min_prob: segForm.min_prob,
      max_prob: segForm.max_prob,
      band: segForm.band || null,
      description: segForm.description || null,
    })
    tip('ok', '人群包创建成功')
    Object.assign(segForm, { name: '', source_job_id: null, min_prob: 0.6, max_prob: null, band: '', description: '' })
    await loadSegments()
  } catch (e) {
    tip('error', `人群包创建失败：${errText(e)}`)
  } finally {
    segSubmitting.value = false
  }
}

async function submitReuse() {
  if (!reuseForm.source_segment_id) {
    tip('warn', '请先选择来源人群包')
    return
  }
  if (!reuseForm.name.trim()) {
    tip('warn', '请先填写新人群包名称')
    return
  }
  if (reuseForm.min_prob < 0 || reuseForm.min_prob > 1 || (reuseForm.max_prob !== null && (reuseForm.max_prob < 0 || reuseForm.max_prob > 1 || reuseForm.max_prob < reuseForm.min_prob))) {
    tip('warn', '概率区间不合法：需在 0~1 之间且最小值不大于最大值')
    return
  }
  reuseSubmitting.value = true
  try {
    await reuseAudienceSegment({
      name: reuseForm.name,
      target: segForm.target,
      source_segment_id: reuseForm.source_segment_id,
      min_prob: reuseForm.min_prob,
      max_prob: reuseForm.max_prob,
      band: reuseForm.band || null,
      description: reuseForm.description || null,
    })
    tip('ok', '人群包复用成功')
    Object.assign(reuseForm, { name: '', source_segment_id: null, min_prob: 0.5, max_prob: null, band: '', description: '' })
    await loadSegments()
  } catch (e) {
    tip('error', `人群包复用失败：${errText(e)}`)
  } finally {
    reuseSubmitting.value = false
  }
}

async function changeSegmentStatus(seg: AudienceSegment, status: string) {
  try {
    await patchAudienceSegment(seg.id, { status })
    tip('ok', `人群包已${STATUS_LABEL[status] ?? status}`)
    await loadSegments()
  } catch (e) {
    tip('error', `状态更新失败：${errText(e)}`)
  }
}

async function openSegmentDetail(seg: AudienceSegment) {
  segmentDetail.value = seg
}

/* ---------- 知识库 ---------- */
const docs = ref<KnowledgeDoc[]>([])
const docLoading = ref(false)
const docKeyword = ref('')
const docForm = reactive({
  title: '',
  content: '',
  doc_type: 'guide',
  tags: '',
})
const docSubmitting = ref(false)
const showDocForm = ref(false)
const docDetail = ref<KnowledgeDoc | null>(null)

async function loadDocs(keyword = '') {
  docLoading.value = true
  try {
    const res = keyword
      ? await searchKnowledgeDocs({ keyword, limit: 100 })
      : await fetchKnowledgeDocs({ page: 1, size: 100 })
    docs.value = res.data?.items ?? []
  } catch (e) {
    tip('error', `知识库加载失败：${errText(e)}`)
  } finally {
    docLoading.value = false
  }
}

async function submitDoc() {
  if (!docForm.title.trim()) {
    tip('warn', '请先填写文档标题')
    return
  }
  if (!docForm.content.trim()) {
    tip('warn', '请先填写文档内容')
    return
  }
  docSubmitting.value = true
  try {
    await createKnowledgeDoc({
      title: docForm.title,
      content: docForm.content,
      doc_type: docForm.doc_type,
      tags: docForm.tags.split(/[,，\n]/).map((s) => s.trim()).filter(Boolean),
    })
    tip('ok', '知识文档已沉淀')
    Object.assign(docForm, { title: '', content: '', doc_type: 'guide', tags: '' })
    showDocForm.value = false
    await loadDocs(docKeyword.value)
  } catch (e) {
    tip('error', `知识沉淀失败：${errText(e)}`)
  } finally {
    docSubmitting.value = false
  }
}

async function removeDoc(doc: KnowledgeDoc) {
  if (!window.confirm(`确认删除知识文档「${doc.title}」？删除后不可恢复。`)) return
  try {
    await deleteKnowledgeDoc(doc.id)
    tip('ok', '知识文档已删除')
    if (docDetail.value?.id === doc.id) docDetail.value = null
    await loadDocs(docKeyword.value)
  } catch (e) {
    tip('error', `删除失败：${errText(e)}`)
  }
}

/* ---------- 智能体 ---------- */
const agents = ref<AgentRun[]>([])
const agentLoading = ref(false)
const agentForm = reactive({
  name: '',
  scenario: '',
  approval_required: true,
})
const agentSubmitting = ref(false)
const agentDetail = ref<AgentRun | null>(null)
const agentDetailLoading = ref(false)

async function loadAgents() {
  agentLoading.value = true
  try {
    const res = await fetchAgentRuns({ page: 1, size: 100 })
    agents.value = res.data?.items ?? []
  } catch (e) {
    tip('error', `智能体任务加载失败：${errText(e)}`)
  } finally {
    agentLoading.value = false
  }
}

async function submitAgent() {
  if (!agentForm.name.trim()) {
    tip('warn', '请先填写任务名称')
    return
  }
  agentSubmitting.value = true
  try {
    const res = await createAgentRun({
      name: agentForm.name,
      scenario: agentForm.scenario,
      approval_required: agentForm.approval_required,
    })
    tip('ok', `智能体任务「${res.data?.name ?? ''}」已创建`)
    Object.assign(agentForm, { name: '', scenario: '', approval_required: true })
    await loadAgents()
  } catch (e) {
    tip('error', `智能体任务创建失败：${errText(e)}`)
  } finally {
    agentSubmitting.value = false
  }
}

async function openAgentDetail(run: AgentRun) {
  agentDetailLoading.value = true
  agentDetail.value = run
  try {
    const res = await fetchAgentRun(run.id)
    agentDetail.value = res.data
  } catch (e) {
    tip('error', `智能体详情加载失败：${errText(e)}`)
  } finally {
    agentDetailLoading.value = false
  }
}

async function doAnalyze(run: AgentRun) {
  try {
    const res = await analyzeAgentRun(run.id)
    tip('ok', '智能体已完成分析')
    agentDetail.value = res.data
    await loadAgents()
  } catch (e) {
    tip('error', `分析失败：${errText(e)}`)
  }
}

async function doComplete(run: AgentRun) {
  if (!window.confirm('确认将该智能体任务标记为完成？')) return
  try {
    const res = await completeAgentRun(run.id)
    tip('ok', '智能体任务已完成')
    agentDetail.value = res.data
    await loadAgents()
  } catch (e) {
    tip('error', `完成操作失败：${errText(e)}`)
  }
}

async function changeAgentStatus(run: AgentRun, status: string) {
  try {
    await patchAgentRun(run.id, { status })
    tip('ok', `智能体状态已更新为${STATUS_LABEL[status] ?? status}`)
    await loadAgents()
  } catch (e) {
    tip('error', `状态更新失败：${errText(e)}`)
  }
}

const stats = computed(() => ({
  runs: runs.value.length,
  running: runs.value.filter((r) => r.status === 'running' || r.status === 'pending').length,
  segments: segments.value.length,
  docs: docs.value.length,
  agents: agents.value.length,
  awaiting: agents.value.filter((r) => r.status === 'awaiting_approval' || r.status === 'analyzing').length,
}))

onMounted(async () => {
  await Promise.all([loadRuns(), loadSegments(), loadDocs(), loadAgents()])
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>洞察中心</h1>
        <p class="page-sub">预测 · 人群 · 知识 · 智能体 —— 一站式运营决策工作台</p>
      </div>
      <div class="head-actions">
        <button class="btn" @click="switchTab('prediction')">发起预测</button>
        <button class="btn primary" @click="switchTab('agent')">新建智能体</button>
      </div>
    </div>

    <div v-if="msg.text" class="msg" :class="msg.type">{{ msg.text }}</div>

    <!-- 统计导航 -->
    <div class="stat-row">
      <button class="stat-card" :class="{ active: tab === 'prediction' }" @click="switchTab('prediction')">
        <span class="stat-num">{{ stats.runs }}</span>
        <span class="stat-label">预测任务</span>
        <span v-if="stats.running" class="stat-hint">运行中 {{ stats.running }}</span>
      </button>
      <button class="stat-card" :class="{ active: tab === 'audience' }" @click="switchTab('audience')">
        <span class="stat-num">{{ stats.segments }}</span>
        <span class="stat-label">人群包</span>
      </button>
      <button class="stat-card" :class="{ active: tab === 'knowledge' }" @click="switchTab('knowledge')">
        <span class="stat-num">{{ stats.docs }}</span>
        <span class="stat-label">知识文档</span>
      </button>
      <button class="stat-card" :class="{ active: tab === 'agent' }" @click="switchTab('agent')">
        <span class="stat-num">{{ stats.agents }}</span>
        <span class="stat-label">智能体任务</span>
        <span v-if="stats.awaiting" class="stat-hint warn">待处理 {{ stats.awaiting }}</span>
      </button>
    </div>

    <div class="tab-bar">
      <button class="tab" :class="{ active: tab === 'prediction' }" @click="switchTab('prediction')">流失/转化预测</button>
      <button class="tab" :class="{ active: tab === 'audience' }" @click="switchTab('audience')">人群包管理</button>
      <button class="tab" :class="{ active: tab === 'knowledge' }" @click="switchTab('knowledge')">知识库</button>
      <button class="tab" :class="{ active: tab === 'agent' }" @click="switchTab('agent')">智能体工作台</button>
    </div>

    <!-- ================= 预测模块 ================= -->
    <section v-show="tab === 'prediction'" class="module-grid two-col">
      <div class="card">
        <div class="card-head">
          <h3>发起预测</h3>
          <span class="hint">填写任务并提交，系统将自动完成分析与评分</span>
        </div>
        <form class="form" @submit.prevent="submitPrediction">
          <div class="field">
            <label>任务名称 <em>*</em></label>
            <input v-model="predForm.name" class="input" placeholder="例如：Q4 流失预警" required />
          </div>
          <div class="field">
            <label>预测目标</label>
            <div class="seg-group">
              <button type="button" class="seg" :class="{ on: predForm.target === 'churn' }" @click="predForm.target = 'churn'">流失预测</button>
              <button type="button" class="seg" :class="{ on: predForm.target === 'conversion' }" @click="predForm.target = 'conversion'">转化预测</button>
            </div>
          </div>
          <div class="row">
            <div class="field grow">
              <label>运行模式</label>
              <select v-model="predForm.mode" class="input">
                <option value="local">本地执行</option>
                <option value="api">接口执行</option>
                <option value="rule">规则执行</option>
              </select>
            </div>
            <div class="field grow">
              <label>判定阈值</label>
              <input v-model.number="predForm.threshold" class="input" type="number" min="0" max="1" step="0.05" />
            </div>
          </div>
          <div class="field">
            <label>观察对象（用户ID，逗号/换行分隔）</label>
            <textarea v-model="predKeysText" class="input area" rows="3" placeholder="可选。留空则对全量用户评分"></textarea>
          </div>
          <label class="check"><input v-model="predForm.rule_fallback" type="checkbox" /> 规则兜底（数据不足时按规则回退）</label>
          <button class="btn primary block" type="submit" :disabled="predSubmitting">
            {{ predSubmitting ? '提交中…' : '发起预测' }}
          </button>
        </form>
      </div>

      <div class="card">
        <div class="card-head">
          <h3>预测任务列表</h3>
          <button class="btn ghost sm" @click="loadRuns">刷新</button>
        </div>
        <div v-if="runsLoading" class="loading">加载中…</div>
        <div v-else-if="!runs.length" class="empty">
          <p class="empty-title">暂无预测任务</p>
          <p class="empty-sub">在左侧填写任务名称，点击「发起预测」即可开始</p>
        </div>
        <table v-else class="table">
          <thead><tr><th>名称</th><th>目标</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="r in runs" :key="r.id">
              <td class="td-main">{{ r.name }}</td>
              <td><span class="tag">{{ r.target === 'churn' ? '流失' : '转化' }}</span></td>
              <td><span class="badge" :class="stCls(r.status)">{{ stLabel(r.status) }}</span></td>
              <td class="td-muted">{{ dt(r.created_at) }}</td>
              <td><button class="btn ghost sm" @click="openPredDetail(r)">查看</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ================= 人群模块 ================= -->
    <section v-show="tab === 'audience'" class="module-grid two-col">
      <div class="card">
        <div class="card-head">
          <h3>人群包</h3>
          <button class="btn ghost sm" @click="showReuse = !showReuse">{{ showReuse ? '收起复用' : '复用已有包' }}</button>
        </div>

        <form v-if="!showReuse" class="form" @submit.prevent="submitSegment">
          <div class="field">
            <label>人群包名称 <em>*</em></label>
            <input v-model="segForm.name" class="input" placeholder="例如：高流失风险用户" required />
          </div>
          <div class="row">
            <div class="field grow">
              <label>目标类型</label>
              <select v-model="segForm.target" class="input">
                <option value="churn">流失</option>
                <option value="conversion">转化</option>
              </select>
            </div>
            <div class="field grow">
              <label>来源预测任务</label>
              <select v-model="segForm.source_job_id" class="input">
                <option :value="null">自动选择</option>
                <option v-for="r in runs" :key="r.id" :value="r.id">{{ r.name }}</option>
              </select>
            </div>
          </div>
          <div class="row">
            <div class="field grow">
              <label>最小概率</label>
              <input v-model.number="segForm.min_prob" class="input" type="number" min="0" max="1" step="0.05" />
            </div>
            <div class="field grow">
              <label>最大概率（可选）</label>
              <input v-model.number="segForm.max_prob" class="input" type="number" min="0" max="1" step="0.05" />
            </div>
            <div class="field grow">
              <label>概率档位</label>
              <select v-model="segForm.band" class="input">
                <option value="">不限</option>
                <option value="high">高概率</option>
                <option value="medium">中概率</option>
                <option value="low">低概率</option>
              </select>
            </div>
          </div>
          <div class="field">
            <label>描述（可选）</label>
            <textarea v-model="segForm.description" class="input area" rows="2" placeholder="说明该人群的用途"></textarea>
          </div>
          <button class="btn primary block" type="submit" :disabled="segSubmitting">
            {{ segSubmitting ? '创建中…' : '创建人群包' }}
          </button>
        </form>

        <form v-else class="form" @submit.prevent="submitReuse">
          <div class="field">
            <label>新人群包名称 <em>*</em></label>
            <input v-model="reuseForm.name" class="input" placeholder="例如：Q4 高价值流失（复用）" required />
          </div>
          <div class="field">
            <label>来源人群包 <em>*</em></label>
            <select v-model="reuseForm.source_segment_id" class="input" required>
              <option :value="null">请选择</option>
              <option v-for="s in segments" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
          <div class="row">
            <div class="field grow">
              <label>最小概率</label>
              <input v-model.number="reuseForm.min_prob" class="input" type="number" min="0" max="1" step="0.05" />
            </div>
            <div class="field grow">
              <label>最大概率（可选）</label>
              <input v-model.number="reuseForm.max_prob" class="input" type="number" min="0" max="1" step="0.05" />
            </div>
            <div class="field grow">
              <label>概率档位</label>
              <select v-model="reuseForm.band" class="input">
                <option value="">不限</option>
                <option value="high">高概率</option>
                <option value="medium">中概率</option>
                <option value="low">低概率</option>
              </select>
            </div>
          </div>
          <div class="field">
            <label>描述（可选）</label>
            <textarea v-model="reuseForm.description" class="input area" rows="2"></textarea>
          </div>
          <button class="btn primary block" type="submit" :disabled="reuseSubmitting">
            {{ reuseSubmitting ? '复用中…' : '复用生成' }}
          </button>
        </form>
      </div>

      <div class="card">
        <div class="card-head">
          <h3>人群包列表</h3>
          <button class="btn ghost sm" @click="loadSegments">刷新</button>
        </div>
        <div v-if="segLoading" class="loading">加载中…</div>
        <div v-else-if="!segments.length" class="empty">
          <p class="empty-title">暂无人群包</p>
          <p class="empty-sub">创建人群包后，可在智能体任务中直接引用</p>
        </div>
        <table v-else class="table">
          <thead><tr><th>名称</th><th>目标</th><th>规模</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="s in segments" :key="s.id">
              <td class="td-main">{{ s.name }}</td>
              <td><span class="tag">{{ s.target === 'churn' ? '流失' : '转化' }}</span></td>
              <td>{{ s.member_count ?? '-' }} 人</td>
              <td><span class="badge" :class="stCls(s.status)">{{ stLabel(s.status) }}</span></td>
              <td class="ops">
                <button class="btn ghost sm" @click="openSegmentDetail(s)">详情</button>
                <button v-if="s.status === 'ready'" class="btn ghost sm" @click="changeSegmentStatus(s, 'active')">启用</button>
                <button v-else-if="s.status === 'active'" class="btn ghost sm warn-text" @click="changeSegmentStatus(s, 'expired')">停用</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ================= 知识模块 ================= -->
    <section v-show="tab === 'knowledge'" class="module-grid two-col">
      <div class="card">
        <div class="card-head">
          <h3>知识沉淀</h3>
          <button class="btn ghost sm" @click="showDocForm = !showDocForm">{{ showDocForm ? '收起' : '新增文档' }}</button>
        </div>
        <form v-if="showDocForm" class="form" @submit.prevent="submitDoc">
          <div class="field">
            <label>标题 <em>*</em></label>
            <input v-model="docForm.title" class="input" placeholder="例如：Q4 促销活动复盘" required />
          </div>
          <div class="field">
            <label>分类</label>
            <select v-model="docForm.doc_type" class="input">
              <option value="guide">运营指南</option>
              <option value="case">案例复盘</option>
              <option value="strategy">策略库</option>
              <option value="other">其他</option>
            </select>
          </div>
          <div class="field">
            <label>内容 <em>*</em></label>
            <textarea v-model="docForm.content" class="input area" rows="7" placeholder="沉淀经验、结论与操作要点"></textarea>
          </div>
          <div class="field">
            <label>标签（逗号分隔，可选）</label>
            <input v-model="docForm.tags" class="input" placeholder="例如：促销,复盘,转化" />
          </div>
          <button class="btn primary block" type="submit" :disabled="docSubmitting">
            {{ docSubmitting ? '保存中…' : '保存文档' }}
          </button>
        </form>
        <div v-else class="tip-box">点击「新增文档」记录运营经验，可在搜索框中快速检索历史结论。</div>
      </div>

      <div class="card">
        <div class="card-head">
          <h3>知识文档</h3>
          <div class="search-row">
            <input v-model="docKeyword" class="input grow" placeholder="搜索标题 / 内容 / 标签" @keyup.enter="loadDocs(docKeyword)" />
            <button class="btn" @click="loadDocs(docKeyword)">搜索</button>
            <button v-if="docKeyword" class="btn ghost" @click="docKeyword = ''; loadDocs('')">清除</button>
          </div>
        </div>
        <div v-if="docLoading" class="loading">加载中…</div>
        <div v-else-if="!docs.length" class="empty">
          <p class="empty-title">{{ docKeyword ? '未找到匹配文档' : '暂无知识文档' }}</p>
          <p class="empty-sub">{{ docKeyword ? '换个关键词试试' : '沉淀第一篇运营经验吧' }}</p>
        </div>
        <table v-else class="table">
          <thead><tr><th>标题</th><th>分类</th><th>标签</th><th>更新时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="d in docs" :key="d.id">
              <td class="td-main">{{ d.title }}</td>
              <td><span class="tag">{{ d.doc_type }}</span></td>
              <td class="td-muted">{{ (d.tags ?? []).join(', ') || '-' }}</td>
              <td class="td-muted">{{ dt(d.updated_at || d.created_at) }}</td>
              <td class="ops">
                <button class="btn ghost sm" @click="docDetail = d">详情</button>
                <button class="btn ghost sm danger-text" @click="removeDoc(d)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ================= 智能体模块 ================= -->
    <section v-show="tab === 'agent'" class="module-grid two-col">
      <div class="card">
        <div class="card-head">
          <h3>新建智能体任务</h3>
          <span class="hint">配置任务后可自动分析、产出策略并等待审批</span>
        </div>
        <form class="form" @submit.prevent="submitAgent">
          <div class="field">
            <label>任务名称 <em>*</em></label>
            <input v-model="agentForm.name" class="input" placeholder="例如：11 月增长策略" required />
          </div>
          <div class="field">
            <label>任务场景描述</label>
            <textarea v-model="agentForm.scenario" class="input area" rows="4" placeholder="描述要解决的问题或希望达成的目标"></textarea>
          </div>
          <label class="check"><input v-model="agentForm.approval_required" type="checkbox" /> 需要人工审批后执行</label>
          <button class="btn primary block" type="submit" :disabled="agentSubmitting">
            {{ agentSubmitting ? '创建中…' : '创建智能体任务' }}
          </button>
        </form>
      </div>

      <div class="card">
        <div class="card-head">
          <h3>智能体任务列表</h3>
          <button class="btn ghost sm" @click="loadAgents">刷新</button>
        </div>
        <div v-if="agentLoading" class="loading">加载中…</div>
        <div v-else-if="!agents.length" class="empty">
          <p class="empty-title">暂无智能体任务</p>
          <p class="empty-sub">创建任务后，智能体将自动执行分析并给出策略建议</p>
        </div>
        <table v-else class="table">
          <thead><tr><th>名称</th><th>场景</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="a in agents" :key="a.id">
              <td class="td-main">{{ a.name }}</td>
              <td class="td-muted">{{ a.scenario || '-' }}</td>
              <td><span class="badge" :class="stCls(a.status)">{{ stLabel(a.status) }}</span></td>
              <td class="td-muted">{{ dt(a.created_at) }}</td>
              <td class="ops">
                <button class="btn ghost sm" @click="openAgentDetail(a)">查看</button>
                <button v-if="a.status === 'awaiting_approval'" class="btn ghost sm warn-text" @click="doComplete(a)">审批通过</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ============ 弹层：预测详情 ============ -->
    <div v-if="predDetail" class="mask" @click.self="predDetail = null">
      <div class="drawer">
        <div class="drawer-head">
          <div class="drawer-title">
            <h3>{{ predDetail.name }}</h3>
            <span class="badge" :class="stCls(predDetail.status)">{{ stLabel(predDetail.status) }}</span>
          </div>
          <button class="btn ghost sm" @click="predDetail = null">关闭</button>
        </div>
        <div v-if="predDetailLoading" class="loading">加载中…</div>
        <template v-else>
          <p class="meta-line">目标：{{ predDetail.target === 'churn' ? '流失预测' : '转化预测' }} · 模式：{{ predDetail.mode }} · 阈值：{{ predDetail.threshold }}</p>
          <p class="meta-line">创建：{{ dt(predDetail.created_at) }}</p>
          <div class="band-row">
            <div class="band high">高概率 {{ bandCount(predDetail.results, 'high') }} 人</div>
            <div class="band medium">中概率 {{ bandCount(predDetail.results, 'medium') }} 人</div>
            <div class="band low">低概率 {{ bandCount(predDetail.results, 'low') }} 人</div>
          </div>
          <h4>评分明细（{{ (predDetail.results ?? []).length }} 条）</h4>
          <div class="table-scroll">
            <table class="table">
              <thead><tr><th>对象</th><th>概率</th><th>档位</th></tr></thead>
              <tbody>
                <tr v-for="(it, i) in (predDetail.results ?? [])" :key="i">
                  <td class="td-main">{{ it.subject_key }}</td>
                  <td>{{ pct(it.probability) }}</td>
                  <td><span class="badge" :class="stCls(it.band)">{{ stLabel(it.band) }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>
    </div>

    <!-- ============ 弹层：人群详情 ============ -->
    <div v-if="segmentDetail" class="mask" @click.self="segmentDetail = null">
      <div class="drawer">
        <div class="drawer-head">
          <div>
            <h3>{{ segmentDetail.name }}</h3>
            <span class="badge" :class="stCls(segmentDetail.status)">{{ stLabel(segmentDetail.status) }}</span>
          </div>
          <button class="btn ghost sm" @click="segmentDetail = null">关闭</button>
        </div>
        <div class="kv-grid">
          <div class="kv"><span>目标类型</span><b>{{ segmentDetail.target === 'churn' ? '流失' : '转化' }}</b></div>
          <div class="kv"><span>成员规模</span><b>{{ segmentDetail.member_count ?? '-' }} 人</b></div>
          <div class="kv"><span>最小概率</span><b>{{ pct(segmentDetail.min_prob) }}</b></div>
          <div class="kv"><span>最大概率</span><b>{{ pct(segmentDetail.max_prob) }}</b></div>
          <div class="kv"><span>概率档位</span><b>{{ segmentDetail.band ? stLabel(segmentDetail.band) : '-' }}</b></div>
          <div class="kv"><span>来源任务</span><b>{{ segmentDetail.source_job_id ?? '-' }}</b></div>
        </div>
        <div class="field"><label>描述</label><p class="plain">{{ segmentDetail.description || '无' }}</p></div>
        <div class="field">
          <label>成员预览</label>
          <div class="chip-wrap">
            <span v-for="(m, i) in (segmentDetail.members ?? [])" :key="i" class="chip">#{{ m.id }} · {{ pct(m.probability) }}</span>
            <span v-if="!(segmentDetail.members ?? []).length" class="td-muted">暂无成员明细</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ============ 弹层：知识详情 ============ -->
    <div v-if="docDetail" class="mask" @click.self="docDetail = null">
      <div class="drawer">
        <div class="drawer-head">
          <div class="drawer-title">
            <h3>{{ docDetail.title }}</h3>
            <span class="tag">{{ docDetail.doc_type }}</span>
          </div>
          <button class="btn ghost sm" @click="docDetail = null">关闭</button>
        </div>
        <p class="meta-line">更新：{{ dt(docDetail.updated_at || docDetail.created_at) }}</p>
        <div class="doc-content">{{ docDetail.content || '（无内容）' }}</div>
        <div class="chip-wrap">
          <span v-for="t in (docDetail.tags ?? [])" :key="t" class="chip">{{ t }}</span>
        </div>
      </div>
    </div>

    <!-- ============ 弹层：智能体详情 ============ -->
    <div v-if="agentDetail" class="mask" @click.self="agentDetail = null">
      <div class="drawer">
        <div class="drawer-head">
          <div>
            <h3>{{ agentDetail.name }}</h3>
            <span class="badge" :class="stCls(agentDetail.status)">{{ stLabel(agentDetail.status) }}</span>
          </div>
          <button class="btn ghost sm" @click="agentDetail = null">关闭</button>
        </div>
        <div v-if="agentDetailLoading" class="loading">加载中…</div>
        <template v-else>
          <p class="meta-line">创建：{{ dt(agentDetail.created_at) }}</p>
          <div class="field"><label>场景描述</label><p class="plain">{{ agentDetail.scenario || '无' }}</p></div>

          <div class="drawer-ops">
            <button v-if="agentDetail.status === 'awaiting_approval'" class="btn primary" @click="doComplete(agentDetail)">审批通过并完成</button>
            <button v-if="agentDetail.status === 'running' || agentDetail.status === 'pending'" class="btn" @click="doAnalyze(agentDetail)">执行分析</button>
            <button v-if="agentDetail.status !== 'done'" class="btn ghost" @click="changeAgentStatus(agentDetail, 'done')">标记完成</button>
          </div>

          <h4>洞察发现（{{ (agentDetail.insights ?? []).length }}）</h4>
          <div v-if="!(agentDetail.insights ?? []).length" class="empty sm"><p class="empty-sub">暂无洞察，点击「执行分析」生成</p></div>
          <div v-for="(ins, i) in (agentDetail.insights ?? [])" :key="i" class="insight">
            <p><b>{{ ins.title }}</b> <span class="badge" :class="stCls(ins.status)">{{ stLabel(ins.status) }}</span></p>
            <p class="plain">{{ ins.detail || '（无详情）' }}</p>
            <p v-if="ins.suggestion" class="plain">建议：{{ ins.suggestion }}</p>
          </div>

          <h4>行动建议（{{ (agentDetail.actions ?? []).length }}）</h4>
          <div v-if="!(agentDetail.actions ?? []).length" class="empty sm"><p class="empty-sub">暂无行动建议</p></div>
          <div v-for="(ac, i) in (agentDetail.actions ?? [])" :key="i" class="insight">
            <p><b>{{ ac.action_type }}</b> <span class="badge" :class="stCls(ac.status)">{{ stLabel(ac.status) }}</span></p>
            <p v-if="ac.payload" class="plain">{{ JSON.stringify(ac.payload) }}</p>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: var(--space-6);
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}
.page-head h1 {
  margin: 0;
  font-size: 22px;
  line-height: 1.3;
}
.page-sub {
  margin: var(--space-1) 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
}
.head-actions { display: flex; gap: var(--space-2); }

.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 13px;
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}
.btn:hover { background: var(--color-bg-hover); border-color: var(--color-border); }
.btn.primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--color-text-on-primary);
}
.btn.primary:hover { background: var(--color-primary-hover); border-color: var(--color-primary-hover); }
.btn.primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn.ghost { background: transparent; }
.btn.ghost:hover { background: var(--color-bg-hover); }
.btn.sm { padding: 3px 10px; font-size: 12px; border-radius: var(--radius-sm); }
.btn.block { width: 100%; justify-content: center; padding: var(--space-3); }
.warn-text { color: var(--color-warning); }
.danger-text { color: var(--color-error); }

.msg {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-size: 13px;
}
.msg.ok { background: var(--color-success-light); color: var(--color-success); border: 1px solid var(--color-success-border); }
.msg.warn { background: var(--color-warning-light); color: var(--color-warning); border: 1px solid var(--color-warning-border); }
.msg.error { background: var(--color-error-light); color: var(--color-error); border: 1px solid var(--color-error-border); }

.stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--space-3);
}
.stat-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg);
  text-align: left;
  cursor: pointer;
  transition: all var(--transition-fast);
  box-shadow: var(--shadow-sm);
}
.stat-card:hover { border-color: var(--color-primary-border); box-shadow: var(--shadow-card); }
.stat-card.active { border-color: var(--color-primary); background: var(--color-primary-light); }
.stat-num { font-size: 26px; font-weight: 700; line-height: 1.1; color: var(--color-text); }
.stat-label { font-size: 13px; color: var(--color-text-secondary); }
.stat-hint { font-size: 12px; color: var(--color-success); }
.stat-hint.warn { color: var(--color-warning); }

.tab-bar {
  display: flex;
  gap: var(--space-2);
  border-bottom: 2px solid var(--color-border-light);
  padding-bottom: 0;
}
.tab {
  padding: var(--space-2) var(--space-4);
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 14px;
  cursor: pointer;
  margin-bottom: -2px;
}
.tab:hover { color: var(--color-text); }
.tab.active { color: var(--color-primary); border-bottom-color: var(--color-primary); font-weight: 600; }

.module-grid { display: grid; gap: var(--space-5); }
.module-grid.two-col { grid-template-columns: 380px 1fr; }
@media (max-width: 1024px) {
  .module-grid.two-col { grid-template-columns: 1fr; }
}

.card {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-sm);
  min-width: 0;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}
.card-head h3 { margin: 0; font-size: 16px; }
.hint { font-size: 12px; color: var(--color-text-muted); }

.form { display: flex; flex-direction: column; gap: var(--space-4); }
.field { display: flex; flex-direction: column; gap: var(--space-1); }
.field label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.field label em { color: var(--color-error); font-style: normal; }
.input { width: 100%; }
.input.area { resize: vertical; }
.row { display: flex; gap: var(--space-3); }
.row .grow { flex: 1; min-width: 0; }
.seg-group { display: flex; gap: var(--space-2); }
.seg {
  flex: 1;
  padding: var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: 13px;
  cursor: pointer;
}
.seg.on { border-color: var(--color-primary); background: var(--color-primary-light); color: var(--color-primary); font-weight: 600; }
.check { display: flex; align-items: center; gap: var(--space-2); font-size: 13px; color: var(--color-text-secondary); cursor: pointer; }

.badge {
  display: inline-block;
  padding: 1px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.7;
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
}
.badge.ok { background: var(--color-success-light); color: var(--color-success); }
.badge.warn { background: var(--color-warning-light); color: var(--color-warning); }
.badge.error { background: var(--color-error-light); color: var(--color-error); }
.badge.muted { background: var(--color-bg-subtle); color: var(--color-text-muted); }

.tag {
  display: inline-block;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  background: var(--color-primary-light);
  color: var(--color-primary);
}
.tag.danger { background: var(--color-error-light); color: var(--color-error); }

.table { width: 100%; }
.td-main { font-weight: 500; }
.td-muted { color: var(--color-text-muted); font-size: 12px; }
.ops { display: flex; gap: var(--space-1); white-space: nowrap; }

.loading { padding: var(--space-10); text-align: center; color: var(--color-text-muted); }
.empty {
  padding: var(--space-10) var(--space-4);
  text-align: center;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}
.empty.sm { padding: var(--space-4); }
.empty-title { margin: 0 0 var(--space-1); font-weight: 600; color: var(--color-text-secondary); }
.empty-sub { margin: 0; font-size: 12px; color: var(--color-text-muted); }

.tip-box {
  padding: var(--space-4);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
  color: var(--color-text-secondary);
  font-size: 13px;
}
.search-row { display: flex; gap: var(--space-2); min-width: 260px; max-width: 420px; }

.mask {
  position: fixed;
  inset: 0;
  background: var(--mask-overlay);
  display: flex;
  justify-content: flex-end;
  z-index: 100;
}
.drawer {
  width: min(680px, 92vw);
  height: 100%;
  background: var(--color-bg);
  box-shadow: var(--shadow-card);
  padding: var(--space-6);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  animation: slide-in var(--transition-base);
}
@keyframes slide-in {
  from { transform: translateX(24px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  border-bottom: 1px solid var(--color-border-light);
  padding-bottom: var(--space-4);
}
.drawer-title { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.drawer-title h3 { margin: 0; font-size: 18px; }
.drawer-ops { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.meta-line { margin: 0; font-size: 13px; color: var(--color-text-muted); }
.kv-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-3); }
.kv {
  padding: var(--space-3);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.kv span { font-size: 12px; color: var(--color-text-muted); }
.kv b { font-size: 14px; }

.band-row { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.band {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
}
.band.high { background: var(--color-error-light); color: var(--color-error); }
.band.medium { background: var(--color-warning-light); color: var(--color-warning); }
.band.low { background: var(--color-success-light); color: var(--color-success); }

.insight {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  background: var(--color-bg-subtle);
}
.insight p { margin: 0 0 var(--space-1); }
.plain { margin: 0; white-space: pre-wrap; color: var(--color-text-secondary); font-size: 13px; }
.doc-content {
  padding: var(--space-4);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
  white-space: pre-wrap;
  font-size: 13px;
}
.chip-wrap { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.chip {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-size: 12px;
}
</style>
