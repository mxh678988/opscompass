<script setup lang="ts">
// P8 学习进化闭环：决策反馈回流 / 策略权重自调 / 经验案例库 / A-B 对照实验
import { computed, onMounted, reactive, ref } from 'vue'
import {
  archiveCase,
  caseFromFeedback,
  createCase,
  createExperiment,
  createFeedback,
  fetchCases,
  fetchExperiments,
  fetchFeedbacks,
  fetchLearningOverview,
  fetchWeights,
  finishExperiment,
  hitCase,
  patchFeedback,
  recomputeWeights,
  recordSample,
  updateCase,
  updateExperiment,
  type FeedbackItem,
  type LearnCase,
  type LearnExperiment,
  type LearningOverview,
  type PolicyWeight,
} from '@/api/learning'

type TabKey = 'feedback' | 'weight' | 'case' | 'experiment'
const tab = ref<TabKey>('feedback')
const TABS: { key: TabKey; label: string }[] = [
  { key: 'feedback', label: '决策反馈' },
  { key: 'weight', label: '策略权重' },
  { key: 'case', label: '经验案例' },
  { key: 'experiment', label: 'A/B 对照' },
]

const overview = ref<LearningOverview | null>(null)
const feedbacks = ref<FeedbackItem[]>([])
const weights = ref<PolicyWeight[]>([])
const cases = ref<LearnCase[]>([])
const experiments = ref<LearnExperiment[]>([])

const loading = reactive({ overview: false, list: false, submit: false })
const msg = reactive({ type: '', text: '' })
const filters = reactive({ keyword: '', decision: '', outcome: '', caseStatus: '', expStatus: '' })

const showFeedbackForm = ref(false)
const showCaseForm = ref(false)
const showExpForm = ref(false)
const activeFeedback = ref<FeedbackItem | null>(null)
const activeExperiment = ref<LearnExperiment | null>(null)

const DECISIONS = [
  { key: 'adopted', label: '已采纳' },
  { key: 'partial', label: '部分采纳' },
  { key: 'rejected', label: '未采纳' },
  { key: 'ignored', label: '已忽略' },
]
const OUTCOMES = [
  { key: 'success', label: '有效' },
  { key: 'neutral', label: '持平' },
  { key: 'fail', label: '无效' },
  { key: 'unknown', label: '未回填' },
]
const CASE_STATUS = [
  { key: 'draft', label: '草稿' },
  { key: 'verified', label: '已验证' },
  { key: 'archived', label: '已归档' },
]

const EXP_STATUS = [
  { key: 'draft', label: '草稿' },
  { key: 'running', label: '进行中' },
  { key: 'finished', label: '已结项' },
  { key: 'stopped', label: '已停止' },
]

const feedbackForm = reactive({
  policy_code: '',
  action_type: '',
  data_level: 'L1',
  decision: 'adopted',
  outcome: 'success',
  outcome_score: 80,
  effect_note: '',
  remark: '',
})
const patchForm = reactive({
  decision: 'adopted',
  outcome: 'success',
  outcome_score: 80,
  effect_note: '',
})
const adjustForm = reactive({ min_samples: 5, learning_rate: 0.5 })
const caseForm = reactive({
  title: '',
  category: '',
  scenario: '',
  action_taken: '',
  outcome: '',
  outcome_score: 80,
  lesson: '',
  status: 'draft',
  tags: '',
})
const expForm = reactive({
  name: '',
  hypothesis: '',
  metric_code: '',
  variant_a: '',
  variant_b: '',
  status: 'draft',
})
const sampleForm = reactive({ variant: 'a', result: 0 })
const finishForm = reactive({ winner: '', conclusion: '' })

const summary = computed(() => {
  const o = overview.value
  if (!o) return [] as { label: string; value: string }[]
  return [
    { label: '反馈总数', value: String(o.feedback_total) },
    { label: '采纳率', value: pct(o.adopt_rate) },
    { label: '有效率', value: pct(o.success_rate) },
    { label: '平均效果分', value: o.avg_score ? o.avg_score.toFixed(1) : '-' },
    { label: '策略权重数', value: String(o.weight_total) },
    { label: '经验案例数', value: String(o.case_total) },
    { label: '实验总数', value: `${o.experiment_total} / 进行中 ${o.experiment_running}` },
  ]
})

function tip(type: string, text: string) {
  msg.type = type
  msg.text = text
}
function errText(e: any): string {
  return e?.response?.data?.message || e?.message || '请求失败'
}
function pct(v?: number | null) {
  return v === null || v === undefined ? '-' : `${(Number(v) * 100).toFixed(1)}%`
}
function num(v?: number | null, digits = 2) {
  return v === null || v === undefined ? '-' : Number(v).toFixed(digits)
}
function dt(v?: string | null) {
  return v ? String(v).replace('T', ' ').slice(0, 19) : '-'
}
function labelOf(list: { key: string; label: string }[], key?: string | null) {
  return list.find((i) => i.key === key)?.label ?? key ?? '-'
}
function winnerText(v?: string | null) {
  if (!v || v === 'none') return '无显著差异'
  return v === 'a' ? '方案 A 胜出' : v === 'b' ? '方案 B 胜出' : v
}

async function loadOverview() {
  loading.overview = true
  try {
    const res = await fetchLearningOverview()
    overview.value = res.data
  } catch (e) {
    tip('error', `总览加载失败：${errText(e)}`)
  } finally {
    loading.overview = false
  }
}

async function loadFeedbacks() {
  loading.list = true
  try {
    const res = await fetchFeedbacks({
      keyword: filters.keyword || undefined,
      decision: filters.decision || undefined,
      outcome: filters.outcome || undefined,
      size: 50,
    })
    feedbacks.value = res.data?.items ?? []
  } catch (e) {
    tip('error', `反馈列表加载失败：${errText(e)}`)
  } finally {
    loading.list = false
  }
}

async function loadWeights() {
  loading.list = true
  try {
    const res = await fetchWeights({ keyword: filters.keyword || undefined, size: 50 })
    weights.value = res.data?.items ?? []
  } catch (e) {
    tip('error', `权重列表加载失败：${errText(e)}`)
  } finally {
    loading.list = false
  }
}

async function loadCases() {
  loading.list = true
  try {
    const res = await fetchCases({
      keyword: filters.keyword || undefined,
      status: filters.caseStatus || undefined,
      size: 50,
    })
    cases.value = res.data?.items ?? []
  } catch (e) {
    tip('error', `案例列表加载失败：${errText(e)}`)
  } finally {
    loading.list = false
  }
}

async function loadExperiments() {
  loading.list = true
  try {
    const res = await fetchExperiments({
      keyword: filters.keyword || undefined,
      status: filters.expStatus || undefined,
      size: 50,
    })
    experiments.value = res.data?.items ?? []
  } catch (e) {
    tip('error', `实验列表加载失败：${errText(e)}`)
  } finally {
    loading.list = false
  }
}

function currentLoader() {
  if (tab.value === 'feedback') return loadFeedbacks()
  if (tab.value === 'weight') return loadWeights()
  if (tab.value === 'case') return loadCases()
  return loadExperiments()
}

async function loadAll() {
  await Promise.all([loadOverview(), currentLoader()])
}

onMounted(loadAll)

async function submitFeedback() {
  if (!feedbackForm.policy_code.trim()) {
    tip('warn', '请填写策略编码（权重自调维度）')
    return
  }
  loading.submit = true
  try {
    await createFeedback({
      policy_code: feedbackForm.policy_code.trim(),
      action_type: feedbackForm.action_type.trim(),
      data_level: feedbackForm.data_level,
      decision: feedbackForm.decision,
      outcome: feedbackForm.outcome,
      outcome_score: Number(feedbackForm.outcome_score),
      effect_note: feedbackForm.effect_note,
      remark: feedbackForm.remark,
    })
    tip('ok', '反馈已登记，策略权重已自动刷新')
    showFeedbackForm.value = false
    feedbackForm.effect_note = ''
    feedbackForm.remark = ''
    await loadAll()
  } catch (e) {
    tip('error', `登记失败：${errText(e)}`)
  } finally {
    loading.submit = false
  }
}

function openPatch(row: FeedbackItem) {
  activeFeedback.value = row
  patchForm.decision = row.decision
  patchForm.outcome = row.outcome
  patchForm.outcome_score = row.outcome_score ?? 80
  patchForm.effect_note = row.effect_note ?? ''
}

async function submitPatch() {
  const row = activeFeedback.value
  if (!row) return
  loading.submit = true
  try {
    await patchFeedback(row.id, {
      decision: patchForm.decision,
      outcome: patchForm.outcome,
      outcome_score: Number(patchForm.outcome_score),
      effect_note: patchForm.effect_note,
    })
    tip('ok', '实际效果已补录，权重已重算')
    activeFeedback.value = null
    await loadAll()
  } catch (e) {
    tip('error', `补录失败：${errText(e)}`)
  } finally {
    loading.submit = false
  }
}

async function toCase(row: FeedbackItem) {
  loading.submit = true
  try {
    await caseFromFeedback({
      feedback_id: row.id,
      category: row.policy_code || '',
      lesson: row.effect_note || '',
    })
    tip('ok', '已沉淀为经验案例')
    await loadAll()
  } catch (e) {
    tip('error', `沉淀失败：${errText(e)}`)
  } finally {
    loading.submit = false
  }
}

async function doRecompute() {
  loading.submit = true
  try {
    const res = await recomputeWeights({
      min_samples: Number(adjustForm.min_samples),
      learning_rate: Number(adjustForm.learning_rate),
    })
    tip('ok', `权重已重算，更新 ${res.data?.updated ?? 0} 条策略`)
    await loadAll()
  } catch (e) {
    tip('error', `重算失败：${errText(e)}`)
  } finally {
    loading.submit = false
  }
}

function switchTab(key: TabKey) {
  tab.value = key
  filters.keyword = ''
  filters.decision = ''
  filters.outcome = ''
  filters.caseStatus = ''
  filters.expStatus = ''
  currentLoader()
}

async function submitCase() {
  if (!caseForm.title.trim()) {
    tip('warn', '请填写案例标题')
    return
  }
  loading.submit = true
  try {
    await createCase({
      title: caseForm.title.trim(),
      category: caseForm.category.trim(),
      tags: caseForm.tags
        ? caseForm.tags
            .split(/[,，\s]+/)
            .filter(Boolean)
        : [],
      scenario: caseForm.scenario,
      action_taken: caseForm.action_taken,
      outcome: caseForm.outcome,
      outcome_score: Number(caseForm.outcome_score),
      lesson: caseForm.lesson,
      status: caseForm.status,
    })
    tip('ok', '经验案例已创建')
    showCaseForm.value = false
    caseForm.title = ''
    caseForm.scenario = ''
    caseForm.action_taken = ''
    caseForm.outcome = ''
    caseForm.lesson = ''
    caseForm.tags = ''
    await loadAll()
  } catch (e) {
    tip('error', `创建失败：${errText(e)}`)
  } finally {
    loading.submit = false
  }
}

async function setCaseStatus(row: LearnCase, status: string) {
  loading.submit = true
  try {
    await updateCase(row.id, { status })
    tip('ok', `案例状态已更新为「${labelOf(CASE_STATUS, status)}」`)
    await loadAll()
  } catch (e) {
    tip('error', `更新失败：${errText(e)}`)
  } finally {
    loading.submit = false
  }
}

async function doHitCase(row: LearnCase) {
  try {
    await hitCase(row.id)
    tip('ok', '已记录一次命中引用')
    await loadCases()
  } catch (e) {
    tip('error', `记录失败：${errText(e)}`)
  }
}

async function doArchiveCase(row: LearnCase) {
  try {
    await archiveCase(row.id)
    tip('ok', '案例已归档')
    await loadAll()
  } catch (e) {
    tip('error', `归档失败：${errText(e)}`)
  }
}

async function submitExperiment() {
  if (!expForm.name.trim()) {
    tip('warn', '请填写实验名称')
    return
  }
  loading.submit = true
  try {
    await createExperiment({
      name: expForm.name.trim(),
      hypothesis: expForm.hypothesis,
      metric_code: expForm.metric_code.trim(),
      variant_a: expForm.variant_a,
      variant_b: expForm.variant_b,
      status: expForm.status,
    })
    tip('ok', '对照实验已创建')
    showExpForm.value = false
    expForm.name = ''
    expForm.hypothesis = ''
    expForm.metric_code = ''
    expForm.variant_a = ''
    expForm.variant_b = ''
    await loadAll()
  } catch (e) {
    tip('error', `创建失败：${errText(e)}`)
  } finally {
    loading.submit = false
  }
}

async function startExperiment(row: LearnExperiment) {
  try {
    await updateExperiment(row.id, { status: 'running' })
    tip('ok', '实验已启动')
    await loadAll()
  } catch (e) {
    tip('error', `启动失败：${errText(e)}`)
  }
}

function openExperiment(row: LearnExperiment) {
  activeExperiment.value = row
  sampleForm.variant = 'a'
  sampleForm.result = 0
  finishForm.winner = ''
  finishForm.conclusion = ''
}

async function submitSample() {
  const row = activeExperiment.value
  if (!row) return
  loading.submit = true
  try {
    const res = await recordSample(row.id, {
      variant: sampleForm.variant,
      result: Number(sampleForm.result),
    })
    tip('ok', `样本已登记，当前提升 ${pct(res.data?.lift)}`)
    activeExperiment.value = res.data
    await loadAll()
  } catch (e) {
    tip('error', `登记失败：${errText(e)}`)
  } finally {
    loading.submit = false
  }
}

async function submitFinish() {
  const row = activeExperiment.value
  if (!row) return
  loading.submit = true
  try {
    await finishExperiment(row.id, {
      winner: finishForm.winner || null,
      conclusion: finishForm.conclusion,
    })
    tip('ok', '实验已结项')
    activeExperiment.value = null
    await loadAll()
  } catch (e) {
    tip('error', `结项失败：${errText(e)}`)
  } finally {
    loading.submit = false
  }
}


</script>

<template>
  <div class="learning">
    <div class="page-head">
      <div>
        <h2>学习进化</h2>
        <p class="sub">决策反馈回流 · 策略权重自调 · 经验案例库 · A/B 对照实验</p>
      </div>
      <div class="head-actions">
        <span class="tag" :class="overview ? 'ok' : 'muted'">
          {{ overview ? `累计反馈 ${overview.feedback_total} 条` : '暂无数据' }}
        </span>
        <button class="btn" :disabled="loading.overview" @click="loadAll">
          {{ loading.overview ? '刷新中…' : '刷新全部' }}
        </button>
      </div>
    </div>

    <p v-if="msg.text" class="msg" :class="msg.type">{{ msg.text }}</p>

    <div class="panel">
      <div class="panel-title">学习总览</div>
      <div v-if="!overview" class="empty">{{ loading.overview ? '加载中…' : '暂无数据' }}</div>
      <template v-else>
        <div class="stat-row">
          <div v-for="s in summary" :key="s.label" class="stat">
            <em>{{ s.value }}</em><span>{{ s.label }}</span>
          </div>
        </div>
        <div v-if="overview.top_weights && overview.top_weights.length" class="sub-block">
          <div class="sub-title">权重 Top（采纳率与效果回填驱动自调）</div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>策略编码</th><th>权重</th><th>基线</th><th>样本</th>
                  <th>采纳</th><th>有效</th><th>有效率</th><th>效果分</th><th>最近调整</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="w in overview.top_weights" :key="w.id">
                  <td class="mono">{{ w.policy_code }}</td>
                  <td><b>{{ num(w.weight, 3) }}</b></td>
                  <td class="muted">{{ num(w.base_weight, 3) }}</td>
                  <td>{{ w.sample_count }}</td>
                  <td>{{ w.adopt_count }}</td>
                  <td>{{ w.success_count }}</td>
                  <td>{{ pct(w.success_rate) }}</td>
                  <td>{{ num(w.avg_score, 1) }}</td>
                  <td class="muted">{{ dt(w.last_adjusted_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </div>

    <div class="tabs">
      <button
        v-for="t in TABS"
        :key="t.key"
        class="tab-btn"
        :class="{ active: tab === t.key }"
        @click="switchTab(t.key)"
      >
        {{ t.label }}
      </button>
    </div>


    <!-- ===== 决策反馈回流 ===== -->
    <div v-if="tab === 'feedback'" class="panel">
      <div class="panel-title">
        决策反馈回流
        <small>登记 AI 建议的采纳情况与实际效果，系统据此自调策略权重</small>
      </div>
      <div class="filters">
        <input
          v-model="filters.keyword"
          class="grow"
          placeholder="按策略编码 / 动作类型搜索"
          @keyup.enter="loadFeedbacks"
        />
        <select v-model="filters.decision">
          <option value="">全部采纳结果</option>
          <option v-for="d in DECISIONS" :key="d.key" :value="d.key">{{ d.label }}</option>
        </select>
        <select v-model="filters.outcome">
          <option value="">全部实际效果</option>
          <option v-for="o in OUTCOMES" :key="o.key" :value="o.key">{{ o.label }}</option>
        </select>
        <button class="btn" :disabled="loading.list" @click="loadFeedbacks">查询</button>
        <button class="btn primary" @click="showFeedbackForm = !showFeedbackForm">
          {{ showFeedbackForm ? '收起登记' : '登记反馈' }}
        </button>
      </div>

      <div v-if="showFeedbackForm" class="sub-block">
        <div class="form">
          <label>策略编码 *<input v-model="feedbackForm.policy_code" placeholder="如 CTR_BOOST" /></label>
          <label>动作类型<input v-model="feedbackForm.action_type" placeholder="如 push / coupon" /></label>
          <label>数据层级
            <select v-model="feedbackForm.data_level">
              <option value="L1">L1</option>
              <option value="L2">L2</option>
              <option value="L3">L3</option>
            </select>
          </label>
          <label>采纳结果
            <select v-model="feedbackForm.decision">
              <option v-for="d in DECISIONS" :key="d.key" :value="d.key">{{ d.label }}</option>
            </select>
          </label>
          <label>实际效果
            <select v-model="feedbackForm.outcome">
              <option v-for="o in OUTCOMES" :key="o.key" :value="o.key">{{ o.label }}</option>
            </select>
          </label>
          <label>效果分（0-100）<input v-model.number="feedbackForm.outcome_score" type="number" min="0" max="100" /></label>
          <label>效果说明<input v-model="feedbackForm.effect_note" placeholder="如 点击率提升 12%" /></label>
          <label>备注<input v-model="feedbackForm.remark" /></label>
          <div class="form-actions">
            <button class="btn primary" :disabled="loading.submit" @click="submitFeedback">提交反馈</button>
            <button class="btn" @click="showFeedbackForm = false">取消</button>
          </div>
        </div>
      </div>

      <div v-if="activeFeedback" class="patch-box">
        <div class="sub-title">
          补录实际效果 · #{{ activeFeedback.id }} {{ activeFeedback.policy_code || '-' }}
        </div>
        <div class="form">
          <label>采纳结果
            <select v-model="patchForm.decision">
              <option v-for="d in DECISIONS" :key="d.key" :value="d.key">{{ d.label }}</option>
            </select>
          </label>
          <label>实际效果
            <select v-model="patchForm.outcome">
              <option v-for="o in OUTCOMES" :key="o.key" :value="o.key">{{ o.label }}</option>
            </select>
          </label>
          <label>效果分<input v-model.number="patchForm.outcome_score" type="number" min="0" max="100" /></label>
          <label>效果说明<input v-model="patchForm.effect_note" /></label>
          <div class="form-actions">
            <button class="btn primary" :disabled="loading.submit" @click="submitPatch">保存并重算权重</button>
            <button class="btn" @click="activeFeedback = null">取消</button>
          </div>
        </div>
      </div>

      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th><th>策略编码</th><th>动作类型</th><th>层级</th><th>采纳结果</th>
              <th>实际效果</th><th>效果分</th><th>效果说明</th><th>登记时间</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in feedbacks" :key="row.id">
              <td class="mono">{{ row.id }}</td>
              <td class="mono">{{ row.policy_code || '-' }}</td>
              <td>{{ row.action_type || '-' }}</td>
              <td>{{ row.data_level || '-' }}</td>
              <td>
                <span class="tag" :class="row.decision === 'adopted' ? 'ok' : row.decision === 'rejected' ? 'bad' : 'muted'">
                  {{ labelOf(DECISIONS, row.decision) }}
                </span>
              </td>
              <td>
                <span class="tag" :class="row.outcome === 'success' ? 'ok' : row.outcome === 'fail' ? 'bad' : 'muted'">
                  {{ labelOf(OUTCOMES, row.outcome) }}
                </span>
              </td>
              <td>{{ row.outcome_score != null ? row.outcome_score : '-' }}</td>
              <td class="ellipsis">{{ row.effect_note || '-' }}</td>
              <td class="muted">{{ dt(row.created_at) }}</td>
              <td class="ops">
                <button class="btn mini" @click="openPatch(row)">补录</button>
                <button class="btn mini" :disabled="loading.submit" @click="toCase(row)">沉淀案例</button>
              </td>
            </tr>
            <tr v-if="!feedbacks.length">
              <td colspan="10" class="empty">{{ loading.list ? '加载中…' : '暂无反馈记录' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ===== 策略权重自调 ===== -->
    <div v-else-if="tab === 'weight'" class="panel">
      <div class="panel-title">
        策略权重自调
        <small>按采纳率 × 效果分梯度调整策略权重，样本不足时先复制基线</small>
      </div>
      <div class="filters">
        <input
          v-model="filters.keyword"
          class="grow"
          placeholder="按策略编码 / 策略名称搜索"
          @keyup.enter="loadWeights"
        />
        <label class="inline">最小样本<input v-model.number="adjustForm.min_samples" type="number" min="1" class="mini-input" /></label>
        <label class="inline">学习率<input v-model.number="adjustForm.learning_rate" type="number" step="0.1" min="0" max="1" class="mini-input" /></label>
        <button class="btn" :disabled="loading.list" @click="loadWeights">查询</button>
        <button class="btn primary" :disabled="loading.submit" @click="doRecompute">触发全量重算</button>
      </div>

      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>策略编码</th><th>策略名称</th><th>动作类型</th><th>权重</th><th>基线</th>
              <th>样本</th><th>采纳</th><th>有效</th><th>有效率</th><th>效果分</th><th>调整说明</th><th>最近调整</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in weights" :key="row.id">
              <td class="mono">{{ row.policy_code }}</td>
              <td>{{ row.policy_name || '-' }}</td>
              <td>{{ row.action_type || '-' }}</td>
              <td><b>{{ num(row.weight, 3) }}</b></td>
              <td class="muted">{{ num(row.base_weight, 3) }}</td>
              <td>{{ row.sample_count }}</td>
              <td>{{ row.adopt_count }}</td>
              <td>{{ row.success_count }}</td>
              <td>{{ pct(row.success_rate) }}</td>
              <td>{{ num(row.avg_score, 1) }}</td>
              <td class="ellipsis">{{ row.adjust_note || '-' }}</td>
              <td class="muted">{{ dt(row.last_adjusted_at) }}</td>
            </tr>
            <tr v-if="!weights.length">
              <td colspan="12" class="empty">{{ loading.list ? '加载中…' : '暂无策略权重，请先登记决策反馈' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ===== 经验案例库 ===== -->
    <div v-else-if="tab === 'case'" class="panel">
      <div class="panel-title">
        经验案例库
        <small>把有效实践沉淀为可复用案例，被引用时累加命中次数</small>
      </div>
      <div class="filters">
        <input
          v-model="filters.keyword"
          class="grow"
          placeholder="按标题 / 案例号 / 分类搜索"
          @keyup.enter="loadCases"
        />
        <select v-model="filters.caseStatus">
          <option value="">全部状态</option>
          <option v-for="s in CASE_STATUS" :key="s.key" :value="s.key">{{ s.label }}</option>
        </select>
        <button class="btn" :disabled="loading.list" @click="loadCases">查询</button>
        <button class="btn primary" @click="showCaseForm = !showCaseForm">
          {{ showCaseForm ? '收起新建' : '新建案例' }}
        </button>
      </div>

      <div v-if="showCaseForm" class="sub-block">
        <div class="form">
          <label>案例标题 *<input v-model="caseForm.title" placeholder="如 大促前 3 天加投信息流" /></label>
          <label>分类<input v-model="caseForm.category" placeholder="如 投放 / 定价 / 留存" /></label>
          <label>标签<input v-model="caseForm.tags" placeholder="逗号分隔，如 大促,信息流" /></label>
          <label>适用场景<input v-model="caseForm.scenario" placeholder="如 流量成本上行期" /></label>
          <label>采取动作<input v-model="caseForm.action_taken" /></label>
          <label>实际结果<input v-model="caseForm.outcome" /></label>
          <label>效果分（0-100）<input v-model.number="caseForm.outcome_score" type="number" min="0" max="100" /></label>
          <label>状态
            <select v-model="caseForm.status">
              <option v-for="s in CASE_STATUS" :key="s.key" :value="s.key">{{ s.label }}</option>
            </select>
          </label>
          <label>经验教训<input v-model="caseForm.lesson" /></label>
          <div class="form-actions">
            <button class="btn primary" :disabled="loading.submit" @click="submitCase">创建案例</button>
            <button class="btn" @click="showCaseForm = false">取消</button>
          </div>
        </div>
      </div>

      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>案例号</th><th>标题</th><th>分类</th><th>标签</th><th>状态</th>
              <th>效果分</th><th>命中</th><th>最近命中</th><th>创建时间</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in cases" :key="row.id">
              <td class="mono">{{ row.case_no }}</td>
              <td>{{ row.title }}</td>
              <td>{{ row.category || '-' }}</td>
              <td>
                <span v-for="t in row.tags" :key="t" class="tag muted">{{ t }}</span>
                <span v-if="!row.tags || !row.tags.length" class="muted">-</span>
              </td>
              <td>
                <span class="tag" :class="row.status === 'verified' ? 'ok' : row.status === 'archived' ? 'muted' : 'warn'">
                  {{ labelOf(CASE_STATUS, row.status) }}
                </span>
              </td>
              <td>{{ row.outcome_score != null ? row.outcome_score : '-' }}</td>
              <td>{{ row.hit_count }}</td>
              <td class="muted">{{ dt(row.last_hit_at) }}</td>
              <td class="muted">{{ dt(row.created_at) }}</td>
              <td class="ops">
                <button class="btn mini" :disabled="loading.submit" @click="doHitCase(row)">命中引用</button>
                <button
                  v-if="row.status !== 'verified'"
                  class="btn mini"
                  :disabled="loading.submit"
                  @click="setCaseStatus(row, 'verified')"
                >验证</button>
                <button
                  v-if="row.status !== 'archived'"
                  class="btn mini danger"
                  :disabled="loading.submit"
                  @click="doArchiveCase(row)"
                >归档</button>
              </td>
            </tr>
            <tr v-if="!cases.length">
              <td colspan="10" class="empty">{{ loading.list ? '加载中…' : '暂无经验案例' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ===== A/B 对照实验 ===== -->
    <div v-else class="panel">
      <div class="panel-title">
        A/B 对照实验
        <small>双方案对照采样，按 lift 与置信度判定胜出并回流权重</small>
      </div>
      <div class="filters">
        <input
          v-model="filters.keyword"
          class="grow"
          placeholder="按实验名称 / 编码搜索"
          @keyup.enter="loadExperiments"
        />
        <select v-model="filters.expStatus">
          <option value="">全部状态</option>
          <option v-for="s in EXP_STATUS" :key="s.key" :value="s.key">{{ s.label }}</option>
        </select>
        <button class="btn" :disabled="loading.list" @click="loadExperiments">查询</button>
        <button class="btn primary" @click="showExpForm = !showExpForm">
          {{ showExpForm ? '收起新建' : '新建实验' }}
        </button>
      </div>

      <div v-if="showExpForm" class="sub-block">
        <div class="form">
          <label>实验名称 *<input v-model="expForm.name" placeholder="如 首页 Banner 文案对照" /></label>
          <label>实验假设<input v-model="expForm.hypothesis" placeholder="如 方案 B 转化率更高" /></label>
          <label>核心指标<input v-model="expForm.metric_code" placeholder="如 CVR / GMV_PER_UV" /></label>
          <label>方案 A<input v-model="expForm.variant_a" placeholder="对照组描述" /></label>
          <label>方案 B<input v-model="expForm.variant_b" placeholder="实验组描述" /></label>
          <label>状态
            <select v-model="expForm.status">
              <option v-for="s in EXP_STATUS" :key="s.key" :value="s.key">{{ s.label }}</option>
            </select>
          </label>
          <div class="form-actions">
            <button class="btn primary" :disabled="loading.submit" @click="submitExperiment">创建实验</button>
            <button class="btn" @click="showExpForm = false">取消</button>
          </div>
        </div>
      </div>

      <div v-if="activeExperiment" class="patch-box">
        <div class="sub-title">
          实验工作台 · {{ activeExperiment.code }} {{ activeExperiment.name }}
        </div>
        <div class="stat-row">
          <div class="stat"><em>{{ activeExperiment.sample_a }}</em><span>方案 A 样本</span></div>
          <div class="stat"><em>{{ activeExperiment.sample_b }}</em><span>方案 B 样本</span></div>
          <div class="stat"><em>{{ num(activeExperiment.result_a, 3) }}</em><span>方案 A 结果</span></div>
          <div class="stat"><em>{{ num(activeExperiment.result_b, 3) }}</em><span>方案 B 结果</span></div>
          <div class="stat"><em>{{ pct(activeExperiment.lift) }}</em><span>提升幅度</span></div>
          <div class="stat"><em>{{ num(activeExperiment.confidence, 2) }}</em><span>置信度</span></div>
          <div class="stat"><em>{{ winnerText(activeExperiment.winner) }}</em><span>胜出判定</span></div>
        </div>
        <div class="form">
          <label>样本方案
            <select v-model="sampleForm.variant">
              <option value="a">方案 A</option>
              <option value="b">方案 B</option>
            </select>
          </label>
          <label>样本结果值<input v-model.number="sampleForm.result" type="number" step="0.01" /></label>
          <div class="form-actions">
            <button class="btn" :disabled="loading.submit" @click="submitSample">登记样本</button>
          </div>
        </div>
        <div class="form">
          <label>胜出方案
            <select v-model="finishForm.winner">
              <option value="">按 lift 自动判定</option>
              <option value="a">方案 A 胜出</option>
              <option value="b">方案 B 胜出</option>
              <option value="none">无显著差异</option>
            </select>
          </label>
          <label>结项结论<input v-model="finishForm.conclusion" /></label>
          <div class="form-actions">
            <button class="btn primary" :disabled="loading.submit" @click="submitFinish">结项</button>
            <button class="btn" @click="activeExperiment = null">关闭工作台</button>
          </div>
        </div>
      </div>

      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>编码</th><th>名称</th><th>指标</th><th>状态</th><th>样本 A/B</th>
              <th>结果 A/B</th><th>提升</th><th>置信度</th><th>胜出</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in experiments" :key="row.id">
              <td class="mono">{{ row.code }}</td>
              <td>{{ row.name }}</td>
              <td class="mono">{{ row.metric_code || '-' }}</td>
              <td>
                <span class="tag" :class="row.status === 'running' ? 'ok' : row.status === 'finished' ? 'muted' : 'warn'">
                  {{ labelOf(EXP_STATUS, row.status) }}
                </span>
              </td>
              <td>{{ row.sample_a }} / {{ row.sample_b }}</td>
              <td>{{ num(row.result_a, 3) }} / {{ num(row.result_b, 3) }}</td>
              <td>{{ pct(row.lift) }}</td>
              <td>{{ num(row.confidence, 2) }}</td>
              <td>{{ winnerText(row.winner) }}</td>
              <td class="ops">
                <button
                  v-if="row.status === 'draft'"
                  class="btn mini"
                  :disabled="loading.submit"
                  @click="startExperiment(row)"
                >启动</button>
                <button class="btn mini" @click="openExperiment(row)">
                  {{ row.status === 'running' ? '登记样本' : '查看' }}
                </button>
              </td>
            </tr>
            <tr v-if="!experiments.length">
              <td colspan="10" class="empty">{{ loading.list ? '加载中…' : '暂无对照实验' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.learning {
  padding: 32px;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
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
  color: var(--color-text);
}
.page-head .sub {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary);
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
  border-radius: var(--radius-sm);
  font-size: 13px;
  border-left: 3px solid var(--color-border);
  background: var(--color-bg-subtle);
}
.msg.ok {
  border-left-color: var(--color-success);
  color: var(--color-success);
}
.msg.warn {
  border-left-color: var(--color-warning);
  color: var(--color-warning);
}
.msg.error {
  border-left-color: var(--color-error);
  color: var(--color-error);
}
.panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 20px;
  background: var(--color-bg);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.panel:hover {
  border-color: var(--color-primary-border);
}
.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 12px;
}
.panel-title small {
  margin-left: 8px;
  font-weight: 400;
  font-size: 12px;
  color: var(--color-text-muted);
}
.sub-block {
  margin-top: 12px;
}
.sub-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--color-text);
}
.stat-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.stat {
  flex: 1 1 110px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-subtle);
  text-align: center;
}
.stat em {
  display: block;
  font-style: normal;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-primary);
}
.stat span {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--color-border-light);
  padding-bottom: 8px;
}
.tab-btn {
  padding: 6px 14px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 500;
}
.tab-btn:hover:not(:disabled) {
  background: var(--color-bg-hover);
  color: var(--color-text);
}
.tab-btn.active {
  background: var(--color-primary-light);
  border-color: var(--color-primary-border);
  color: var(--color-primary);
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.filters .grow {
  flex: 1 1 220px;
  min-width: 160px;
}
.filters label.inline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.mini-input {
  width: 84px;
}
.patch-box {
  margin: 12px 0;
  padding: 12px;
  border: 1px dashed var(--color-primary-border);
  border-radius: var(--radius-md);
  background: var(--color-primary-light);
}
.table-scroll {
  width: 100%;
  max-width: 100%;
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
  border-bottom: 1px solid var(--color-border-light);
  text-align: left;
  vertical-align: middle;
  white-space: nowrap;
}
th {
  font-weight: 600;
  color: var(--color-text-secondary);
  background: var(--color-bg-subtle);
}
tbody tr:hover td {
  background: var(--color-bg-hover);
}
td.ops {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.mono {
  font-family: var(--font-mono);
}
.muted {
  color: var(--color-text-muted);
}
.ellipsis {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empty {
  padding: 16px 0;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-muted);
}

.form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px 16px;
  align-items: center;
}
.form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.form input,
.form select {
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--color-bg);
  color: var(--color-text);
  width: 100%;
}
.form-actions {
  grid-column: 1 / -1;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.btn {
  padding: 5px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 13px;
}
.btn:hover:not(:disabled) {
  border-color: var(--color-primary-border);
  color: var(--color-primary);
}
.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.btn.primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
.btn.primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
  color: #fff;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.22);
}
.btn.mini {
  padding: 3px 8px;
  font-size: 12px;
}
.btn.danger {
  color: var(--color-error);
  border-color: var(--color-error-border);
}
.btn.danger:hover:not(:disabled) {
  background: var(--color-error);
  border-color: var(--color-error);
  color: #fff;
}
.tag {
  display: inline-block;
  padding: 1px 8px;
  margin-right: 4px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
  background: var(--color-bg-subtle);
  color: var(--color-text-muted);
}
.tag.ok {
  background: var(--color-success-light);
  color: var(--color-success);
}
.tag.warn {
  background: var(--color-warning-light);
  color: var(--color-warning);
}
.tag.bad {
  background: var(--color-error-light);
  color: var(--color-error);
}
.tag.muted {
  background: var(--color-bg-subtle);
  color: var(--color-text-muted);
}

/* ===== 响应式自适应（窗口缩放） ===== */
@media (max-width: 1200px) {
  .ellipsis {
    max-width: 140px;
  }
}
@media (max-width: 1024px) {
  .learning {
    padding: 20px 16px;
  }
}
@media (max-width: 768px) {
  .learning {
    padding: 16px 12px;
  }
  .panel {
    padding: 16px;
  }
  .form {
    grid-template-columns: 1fr;
  }
  .filters .grow {
    flex: 1 1 100%;
  }
  .filters > select {
    flex: 1 1 45%;
  }
  .ellipsis {
    max-width: 110px;
  }
  .stat {
    flex: 1 1 90px;
  }
}
@media (max-width: 480px) {
  .learning {
    padding: 12px 10px;
  }
  .page-head h2 {
    font-size: 18px;
  }
  .stat em {
    font-size: 16px;
  }
  .ellipsis {
    max-width: 80px;
  }
}
</style>
