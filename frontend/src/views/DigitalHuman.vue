<template>
  <div class="dh-page">
    <header class="page-head">
      <div>
        <h2>数字人一键生成</h2>
        <p class="sub">形象库 · 音色库 · 四阶段编排（口播稿 → AI 配音 → 数字人驱动 → 成片合成）</p>
      </div>
      <button class="btn ghost" type="button" :disabled="loading" @click="loadAll">
        {{ loading ? '刷新中…' : '刷新' }}
      </button>
    </header>

    <div v-if="error" class="banner bad">{{ error }}</div>
    <div v-if="notice" class="banner ok">{{ notice }}</div>

    <section class="stats" v-if="overview">
      <div class="stat"><span class="k">形象</span><strong>{{ overview.avatars }}</strong></div>
      <div class="stat"><span class="k">音色</span><strong>{{ overview.voices }}</strong></div>
      <div class="stat"><span class="k">工作流</span><strong>{{ overview.workflows }}</strong></div>
      <div class="stat"><span class="k">项目</span><strong>{{ overview.projects }}</strong></div>
      <div class="stat"><span class="k">已完成</span><strong>{{ overview.done }}</strong></div>
      <div class="stat"><span class="k">生成中</span><strong>{{ overview.rendering }}</strong></div>
      <div class="stat"><span class="k">失败</span><strong>{{ overview.failed }}</strong></div>
      <div class="stat"><span class="k">成功率</span><strong>{{ overview.success_rate > 1 ? overview.success_rate.toFixed(1) : (overview.success_rate * 100).toFixed(1) }}%</strong></div>
      <div class="stat"><span class="k">总时长</span><strong>{{ durationText(overview.total_duration_sec) }}</strong></div>
      <div class="stat"><span class="k">演练留痕</span><strong>{{ overview.simulated }}</strong></div>
    </section>

    <section class="engines">
      <div class="eng" v-for="row in engineRows" :key="row.key">
        <div class="eng-top">
          <span class="eng-name">{{ row.label }}</span>
          <span class="dot" :class="row.ready ? 'on' : 'off'"></span>
        </div>
        <div class="eng-engine mono">{{ row.engine }}</div>
        <div class="eng-detail">{{ row.detail || (row.ready ? '引擎就绪' : '未接入，将走演练模式') }}</div>
      </div>
    </section>

    <nav class="tabs">
      <button :class="['tab', { active: tab === 'project' }]" type="button" @click="tab = 'project'">生成项目</button>
      <button :class="['tab', { active: tab === 'avatar' }]" type="button" @click="tab = 'avatar'">形象库</button>
      <button :class="['tab', { active: tab === 'voice' }]" type="button" @click="tab = 'voice'">音色库</button>
      <button :class="['tab', { active: tab === 'workflow' }]" type="button" @click="tab = 'workflow'">工作流模板</button>
    </nav>

    <template v-if="tab === 'project'">
      <div class="card">
        <div class="card-head">
          <h3>新建生成项目</h3>
          <span class="hint">选定形象 / 音色 / 工作流后即可一键生成</span>
        </div>
        <form class="form" @submit.prevent="submitProject">
          <label><span>项目名称</span><input v-model="projectForm.name" placeholder="例：论语十二讲 第 1 期" /></label>
          <label><span>选题 / 主题</span><input v-model="projectForm.topic" placeholder="例：仁者爱人" /></label>
          <label>
            <span>形象</span>
            <select v-model="projectForm.avatar_id">
              <option value="">暂不指定</option>
              <option v-for="a in avatars" :key="a.id" :value="a.id">{{ a.name }}</option>
            </select>
          </label>
          <label>
            <span>音色</span>
            <select v-model="projectForm.voice_id">
              <option value="">暂不指定</option>
              <option v-for="v in voices" :key="v.id" :value="v.id">{{ v.name }}</option>
            </select>
          </label>
          <label>
            <span>工作流</span>
            <select v-model="workflowTarget">
              <option value="">暂不指定</option>
              <option v-for="w in workflows" :key="w.id" :value="w.id">{{ w.name }}</option>
            </select>
          </label>
          <label>
            <span>分辨率</span>
            <select v-model="projectForm.resolution">
              <option v-for="r in RESOLUTIONS" :key="r" :value="r">{{ r }}</option>
            </select>
          </label>
          <label>
            <span>画幅</span>
            <select v-model="projectForm.aspect_ratio">
              <option value="9:16">9:16 竖版</option>
              <option value="16:9">16:9 横版</option>
              <option value="1:1">1:1 方形</option>
            </select>
          </label>
          <label><span>目标时长（秒）</span><input v-model.number="projectForm.duration_sec" type="number" min="5" /></label>
          <label class="check"><input v-model="projectForm.subtitle_enabled" type="checkbox" /><span>生成字幕</span></label>
          <label><span>背景音乐</span><input v-model="projectForm.bgm" placeholder="可选" /></label>
          <label class="wide"><span>素材 / 参考文本</span><textarea v-model="projectForm.source_text" rows="3" placeholder="粘贴原文或要点，AI 据此生成口播稿"></textarea></label>
          <label class="wide"><span>备注</span><input v-model="projectForm.remark" placeholder="可选" /></label>
          <div class="form-actions">
            <button class="btn primary" type="submit" :disabled="busy">{{ busy ? '提交中…' : '创建项目' }}</button>
          </div>
        </form>
      </div>

      <div class="card">
        <div class="card-head">
          <h3>项目列表</h3>
          <div class="filters">
            <input v-model="filter.keyword" placeholder="按名称 / 选题搜索" @keyup.enter="search" />
            <select v-model="filter.status" @change="search">
              <option value="">全部状态</option>
              <option v-for="(label, key) in PROJECT_STATUS" :key="key" :value="key">{{ label }}</option>
            </select>
            <button class="btn ghost" type="button" @click="search">查询</button>
          </div>
        </div>
        <table class="tbl">
          <thead>
            <tr><th>名称</th><th>选题</th><th>状态</th><th>进度</th><th>时长</th><th>画幅</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in projects" :key="row.id" :class="{ picked: detail && detail.id === row.id }">
              <td class="strong">{{ row.name }}</td>
              <td>{{ row.topic || '-' }}</td>
              <td><span class="tag" :class="statusClass(row.status)">{{ PROJECT_STATUS[row.status] || row.status }}</span></td>
              <td class="mono">{{ row.progress || 0 }}%</td>
              <td class="mono">{{ durationText(row.duration_sec) }}</td>
              <td class="mono">{{ row.aspect_ratio || '-' }}</td>
              <td class="ops">
                <button class="btn mini" type="button" @click="openDetail(row)">详情</button>
                <button class="btn mini" type="button" @click="makeScript(row)">口播稿</button>
                <button class="btn mini primary" type="button" @click="oneClick(row)">一键生成</button>
                <button class="btn mini danger" type="button" @click="removeProject(row)">删除</button>
              </td>
            </tr>
            <tr v-if="!projects.length"><td colspan="7" class="empty">暂无项目</td></tr>
          </tbody>
        </table>
        <div class="pager">
          <span class="muted">共 {{ projectTotal }} 条 · 第 {{ page }} 页</span>
          <div>
            <button class="btn mini" type="button" :disabled="page <= 1" @click="turn(-1)">上一页</button>
            <button class="btn mini" type="button" :disabled="page * pageSize >= projectTotal" @click="turn(1)">下一页</button>
          </div>
        </div>
      </div>

      <div class="card" v-if="detail">
        <div class="card-head">
          <h3>项目详情 · {{ detail.name }}</h3>
          <div class="actions">
            <button class="btn mini primary" type="button" :disabled="busy" @click="oneClick(detail)">一键生成</button>
            <button class="btn mini ghost" type="button" @click="detail = null">收起</button>
          </div>
        </div>
        <div class="meta">
          <span>状态：{{ PROJECT_STATUS[detail.status] || detail.status }}</span>
          <span>进度：{{ detail.progress || 0 }}%</span>
          <span>画幅：{{ detail.aspect_ratio }}</span>
          <span>时长：{{ durationText(detail.duration_sec) }}</span>
          <span>字幕：{{ detail.subtitle_enabled ? '开' : '关' }}</span>
          <span>模型：{{ detail.ai_model || '-' }}</span>
          <span v-if="detail.simulated" class="warn-text">演练模式</span>
          <span v-if="detail.error" class="bad-text">{{ detail.error }}</span>
        </div>
        <div class="script-panel">
          <div class="panel-head">
            <h4>口播稿</h4>
            <button class="btn mini" type="button" :disabled="busy" @click="saveScriptText">保存</button>
          </div>
          <textarea v-model="detail.script" rows="8"></textarea>
        </div>
        <form class="form inline" @submit.prevent="makeScript(detail)">
          <label><span>语气</span><input v-model="scriptForm.tone" /></label>
          <label><span>风格</span><input v-model="scriptForm.style" /></label>
          <label><span>分镜数</span><input v-model.number="scriptForm.segment_count" type="number" min="1" /></label>
          <label><span>目标秒数</span><input v-model.number="scriptForm.target_sec" type="number" min="10" /></label>
          <label class="wide"><span>关键词</span><input v-model="scriptForm.keywords" placeholder="逗号分隔，可选" /></label>
          <div class="form-actions">
            <button class="btn primary" type="submit" :disabled="busy">重写口播稿</button>
          </div>
        </form>
        <div class="segs" v-if="detail.segments && detail.segments.length">
          <div class="seg" v-for="(s, i) in detail.segments" :key="i">
            <span class="seg-idx">{{ s.index || i + 1 }}</span>
            <div class="seg-body">
              <strong>{{ s.title || '分镜' }}</strong>
              <p>{{ s.content }}</p>
              <span class="muted" v-if="s.seconds">约 {{ s.seconds }} 秒</span>
            </div>
          </div>
        </div>
        <table class="tbl" v-if="detail.tasks && detail.tasks.length">
          <thead><tr><th>阶段</th><th>状态</th><th>进度</th><th>引擎</th><th>产出</th><th>耗时</th></tr></thead>
          <tbody>
            <tr v-for="t in detail.tasks" :key="t.id">
              <td>{{ t.stage_name || STAGE_LABEL[t.stage] || t.stage }}</td>
              <td><span class="tag" :class="taskClass(t.status)">{{ TASK_STATUS[t.status] || t.status }}</span></td>
              <td class="mono">{{ t.progress || 0 }}%</td>
              <td class="mono">{{ t.engine || '-' }}</td>
              <td class="mono">{{ t.output_url || t.message || '-' }}</td>
              <td class="mono">{{ t.duration_ms ? (t.duration_ms / 1000).toFixed(1) + 's' : '-' }}</td>
            </tr>
          </tbody>
        </table>
        <div class="out" v-if="detail.video_url || detail.audio_url || detail.cover_url">
          <span v-if="detail.video_url">成片：<a :href="detail.video_url" target="_blank">{{ detail.video_url }}</a></span>
          <span v-if="detail.audio_url">音频：<a :href="detail.audio_url" target="_blank">{{ detail.audio_url }}</a></span>
          <span v-if="detail.cover_url">封面：<a :href="detail.cover_url" target="_blank">{{ detail.cover_url }}</a></span>
        </div>
      </div>
    </template>

    <template v-if="tab === 'avatar'">
      <div class="card">
        <div class="card-head"><h3>新增形象</h3></div>
        <form class="form" @submit.prevent="submitAvatar">
          <label><span>名称</span><input v-model="avatarForm.name" placeholder="例：老孟-正装" /></label>
          <label>
            <span>类型</span>
            <select v-model="avatarForm.avatar_type">
              <option v-for="t in AVATAR_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </label>
          <label>
            <span>性别</span>
            <select v-model="avatarForm.gender">
              <option value="neutral">中性</option>
              <option value="male">男</option>
              <option value="female">女</option>
            </select>
          </label>
          <label><span>风格</span><input v-model="avatarForm.style" placeholder="例：国风、商务" /></label>
          <label class="wide"><span>预览图 / 素材 URL</span><input v-model="avatarForm.preview_url" placeholder="本地路径或链接" /></label>
          <label class="wide"><span>备注</span><input v-model="avatarForm.remark" /></label>
          <div class="form-actions"><button class="btn primary" type="submit" :disabled="busy">保存形象</button></div>
        </form>
      </div>

      <div class="card">
        <div class="card-head">
          <h3>形象库</h3>
          <span class="hint">共 {{ avatars.length }} 个</span>
        </div>
        <div class="grid">
          <div class="tile" v-for="a in avatars" :key="a.id">
            <img v-if="a.preview_url" :src="a.preview_url" :alt="a.name" />
            <div class="tile-name">{{ a.name }}</div>
            <div class="tile-meta">{{ a.avatar_type }} · {{ a.gender }} · {{ a.style || '默认风格' }}</div>
            <div class="tile-meta mono">{{ a.engine || '-' }} · {{ a.status }}</div>
            <div class="tile-path mono">{{ a.preview_url || '-' }}</div>
            <button class="btn mini danger" type="button" @click="removeAvatar(a)">删除</button>
          </div>
          <div class="empty" v-if="!avatars.length">暂无形象，先在上方新增</div>
        </div>
      </div>
    </template>

    <template v-if="tab === 'voice'">
      <div class="card">
        <div class="card-head"><h3>新增音色</h3></div>
        <form class="form" @submit.prevent="submitVoice">
          <label><span>名称</span><input v-model="voiceForm.name" placeholder="例：沉稳男声" /></label>
          <label><span>引擎</span><input v-model="voiceForm.engine" placeholder="例：edge-tts" /></label>
          <label><span>音色 ID</span><input v-model="voiceForm.voice_id" placeholder="引擎侧音色标识" /></label>
          <label>
            <span>语言</span>
            <select v-model="voiceForm.language">
              <option value="zh-CN">中文（普通话）</option>
              <option value="zh-TW">中文（台湾）</option>
              <option value="en-US">英语（美）</option>
              <option value="ja-JP">日语</option>
            </select>
          </label>
          <label>
            <span>性别</span>
            <select v-model="voiceForm.gender">
              <option value="female">女</option>
              <option value="male">男</option>
              <option value="neutral">中性</option>
            </select>
          </label>
          <label><span>语速</span><input v-model="voiceForm.speed" placeholder="1.0" /></label>
          <label class="wide"><span>备注</span><input v-model="voiceForm.remark" /></label>
          <div class="form-actions"><button class="btn primary" type="submit" :disabled="busy">保存音色</button></div>
        </form>
      </div>

      <div class="card">
        <div class="card-head">
          <h3>音色库</h3>
          <span class="hint">共 {{ voices.length }} 个</span>
        </div>
        <table class="tbl">
          <thead><tr><th>名称</th><th>引擎</th><th>音色 ID</th><th>语言</th><th>性别</th><th>语速</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="v in voices" :key="v.id">
              <td class="strong">{{ v.name }}</td>
              <td class="mono">{{ v.engine || '-' }}</td>
              <td class="mono">{{ v.voice_id || '-' }}</td>
              <td class="mono">{{ v.language || '-' }}</td>
              <td>{{ v.gender || '-' }}</td>
              <td class="mono">{{ v.speed || '-' }}</td>
              <td class="ops"><button class="btn mini danger" type="button" @click="removeVoice(v)">删除</button></td>
            </tr>
            <tr v-if="!voices.length"><td colspan="7" class="empty">暂无音色</td></tr>
          </tbody>
        </table>
      </div>
    </template>

    <template v-if="tab === 'workflow'">
      <div class="card">
        <div class="card-head">
          <h3>新建工作流模板</h3>
          <span class="hint">四阶段默认全启用，可按需调整</span>
        </div>
        <form class="form" @submit.prevent="submitWorkflow">
          <label><span>名称</span><input v-model="workflowForm.name" placeholder="例：国学短视频标准流程" /></label>
          <label class="wide"><span>描述</span><input v-model="workflowForm.description" placeholder="可选" /></label>
          <div class="steps">
            <div class="step" v-for="s in stepDraft" :key="s.stage">
              <span class="step-name">{{ s.name }}</span>
              <span class="mono muted">{{ s.stage }}</span>
            </div>
          </div>
          <div class="form-actions"><button class="btn primary" type="submit" :disabled="busy">保存工作流</button></div>
        </form>
      </div>

      <div class="card">
        <div class="card-head">
          <h3>工作流列表</h3>
          <span class="hint">执行前请先在「生成项目」页选定项目</span>
        </div>
        <table class="tbl">
          <thead><tr><th>名称</th><th>阶段</th><th>状态</th><th>执行次数</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="w in workflows" :key="w.id">
              <td class="strong">{{ w.name }}<span v-if="w.is_default" class="tag ok">默认</span></td>
              <td class="mono">{{ (w.steps || []).map(s => s.name || s.stage).join(' → ') || '-' }}</td>
              <td><span class="tag" :class="w.enabled ? 'ok' : ''">{{ w.enabled ? '启用' : '停用' }}</span></td>
              <td class="mono">{{ w.run_count || 0 }}</td>
              <td class="ops">
                <button class="btn mini" type="button" @click="toggleWorkflow(w)">{{ w.enabled ? '停用' : '启用' }}</button>
                <button class="btn mini primary" type="button" @click="execWorkflow(w)">执行</button>
                <button class="btn mini danger" type="button" @click="removeWorkflow(w)">删除</button>
              </td>
            </tr>
            <tr v-if="!workflows.length"><td colspan="5" class="empty">暂无工作流</td></tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
// 数字人一键生成：形象库 / 音色库 / 生成项目（四阶段编排）/ 工作流模板
import { computed, onMounted, reactive, ref } from 'vue'

import {
  createAvatar,
  createProject,
  createVoice,
  createWorkflow,
  deleteAvatar,
  deleteProject,
  deleteVoice,
  deleteWorkflow,
  fetchAvatars,
  fetchEngines,
  fetchOverview,
  fetchProject,
  fetchProjects,
  fetchVoices,
  fetchWorkflows,
  generateScript,
  runGenerate,
  runWorkflow,
  updateProject,
  updateWorkflow,
  type DhAvatar,
  type DhEngineStatus,
  type DhOverview,
  type DhProject,
  type DhVoice,
  type DhWorkflow,
  type WorkflowStep,
} from '@/api/digitalHuman'

const PROJECT_STATUS: Record<string, string> = {
  draft: '草稿',
  scripting: '脚本中',
  ready: '待生成',
  rendering: '生成中',
  done: '已完成',
  failed: '失败',
}

const STAGE_LABEL: Record<string, string> = {
  script: '口播稿',
  voice: 'AI 配音',
  avatar: '数字人驱动',
  compose: '成片合成',
}

const TASK_STATUS: Record<string, string> = {
  pending: '等待',
  running: '进行中',
  success: '成功',
  failed: '失败',
  skipped: '跳过',
}

const AVATAR_TYPES = [
  { value: 'preset', label: '预置形象' },
  { value: 'photo', label: '照片驱动' },
  { value: 'clone', label: '克隆形象' },
]

const RESOLUTIONS = ['720x1280', '1080x1920', '1280x720', '1920x1080']

const tab = ref<'project' | 'avatar' | 'voice' | 'workflow'>('project')
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')

const overview = ref<DhOverview | null>(null)
const engines = ref<DhEngineStatus | null>(null)

const projects = ref<DhProject[]>([])
const projectTotal = ref(0)
const page = ref(1)
const pageSize = 10
const filter = reactive({ keyword: '', status: '' })

const avatars = ref<DhAvatar[]>([])
const voices = ref<DhVoice[]>([])
const workflows = ref<DhWorkflow[]>([])
const detail = ref<DhProject | null>(null)
const workflowTarget = ref<number | ''>('')

const projectForm = reactive({
  name: '',
  topic: '',
  source_text: '',
  avatar_id: '' as string | number,
  voice_id: '' as string | number,
  resolution: '720x1280',
  aspect_ratio: '9:16',
  duration_sec: 60,
  subtitle_enabled: true,
  bgm: '',
  remark: '',
})

const scriptForm = reactive({
  tone: '专业亲和',
  segment_count: 4,
  target_sec: 60,
  style: '中华传统文化',
  keywords: '',
})

const avatarForm = reactive({
  name: '',
  avatar_type: 'preset',
  gender: 'neutral',
  style: '',
  preview_url: '',
  remark: '',
})

const voiceForm = reactive({
  name: '',
  engine: 'edge-tts',
  voice_id: '',
  language: 'zh-CN',
  gender: 'female',
  speed: '1.0',
  remark: '',
})

const workflowForm = reactive({ name: '', description: '', steps: [] as WorkflowStep[] })

const engineRows = computed(() =>
  (['script', 'voice', 'avatar', 'compose'] as const).map((key) => ({
    key,
    label: STAGE_LABEL[key],
    engine: engines.value?.[key]?.engine ?? '-',
    ready: Boolean(engines.value?.[key]?.ready),
    detail: engines.value?.[key]?.detail ?? '',
  })),
)

const stepDraft = computed<WorkflowStep[]>(() =>
  (['script', 'voice', 'avatar', 'compose'] as const).map((stage) => {
    const hit = workflowForm.steps.find((s) => s.stage === stage)
    return hit ?? { stage, name: STAGE_LABEL[stage], engine: '', enabled: true }
  }),
)

function msg(e: any, fallback: string): string {
  return e?.response?.data?.detail ?? e?.message ?? fallback
}

function flash(text: string) {
  notice.value = text
  window.setTimeout(() => {
    if (notice.value === text) notice.value = ''
  }, 3200)
}

async function loadProjects() {
  const res = await fetchProjects({
    keyword: filter.keyword.trim() || undefined,
    status: filter.status || undefined,
    page: page.value,
    size: pageSize,
  })
  projects.value = res.data.items
  projectTotal.value = res.data.total
}

async function loadBasics() {
  const [av, vo, wf] = await Promise.allSettled([
    fetchAvatars({ size: 200 }),
    fetchVoices({ size: 200 }),
    fetchWorkflows({ size: 100 }),
  ])
  if (av.status === 'fulfilled') avatars.value = av.value.data.items
  if (vo.status === 'fulfilled') voices.value = vo.value.data.items
  if (wf.status === 'fulfilled') workflows.value = wf.value.data.items
  const fails: string[] = []
  if (av.status === 'rejected') fails.push(`形象库加载失败：${msg(av.reason, '')}`)
  if (vo.status === 'rejected') fails.push(`音色库加载失败：${msg(vo.reason, '')}`)
  if (wf.status === 'rejected') fails.push(`工作流加载失败：${msg(wf.reason, '')}`)
  if (fails.length) error.value = fails.join('；')
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [ov, en] = await Promise.all([fetchOverview(), fetchEngines()])
    overview.value = ov.data
    engines.value = en.data
    await Promise.all([loadProjects(), loadBasics()])
  } catch (e: any) {
    error.value = msg(e, '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  loadProjects().catch((e) => (error.value = msg(e, '查询失败')))
}

function turn(delta: number) {
  const next = page.value + delta
  if (next < 1 || (next - 1) * pageSize >= projectTotal.value) return
  page.value = next
  loadProjects().catch(() => undefined)
}

async function submitProject() {
  if (!projectForm.name.trim()) {
    error.value = '项目名称必填'
    return
  }
  busy.value = true
  error.value = ''
  try {
    const res = await createProject({
      name: projectForm.name.trim(),
      topic: projectForm.topic.trim(),
      source_text: projectForm.source_text,
      avatar_id: projectForm.avatar_id ? Number(projectForm.avatar_id) : null,
      voice_id: projectForm.voice_id ? Number(projectForm.voice_id) : null,
      workflow_id: workflowTarget.value ? Number(workflowTarget.value) : null,
      resolution: projectForm.resolution,
      aspect_ratio: projectForm.aspect_ratio,
      duration_sec: Number(projectForm.duration_sec) || 0,
      subtitle_enabled: projectForm.subtitle_enabled,
      bgm: projectForm.bgm.trim(),
      remark: projectForm.remark.trim(),
    })
    flash(`项目「${res.data.name}」已创建`)
    Object.assign(projectForm, { name: '', topic: '', source_text: '', bgm: '', remark: '' })
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '创建失败')
  } finally {
    busy.value = false
  }
}

async function makeScript(row: DhProject) {
  busy.value = true
  error.value = ''
  try {
    const res = await generateScript(row.id, {
      tone: scriptForm.tone,
      segment_count: Number(scriptForm.segment_count) || 4,
      target_sec: Number(scriptForm.target_sec) || 60,
      style: scriptForm.style,
      keywords: scriptForm.keywords ? scriptForm.keywords.split(/[，,\s]+/).filter(Boolean) : [],
    })
    flash(res.data.message ?? '口播稿已生成')
    detail.value = res.data.project
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '生成口播稿失败')
  } finally {
    busy.value = false
  }
}

async function oneClick(row: DhProject) {
  busy.value = true
  error.value = ''
  try {
    const res = await runGenerate(row.id, {})
    flash(res.data.message ?? '一键生成完成')
    detail.value = res.data.project
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '一键生成失败')
  } finally {
    busy.value = false
  }
}

async function openDetail(row: DhProject) {
  try {
    const res = await fetchProject(row.id)
    detail.value = res.data
  } catch (e: any) {
    error.value = msg(e, '加载详情失败')
  }
}

async function removeProject(row: DhProject) {
  if (!window.confirm(`确认删除项目「${row.name}」及其阶段留痕？`)) return
  busy.value = true
  try {
    await deleteProject(row.id)
    if (detail.value?.id === row.id) detail.value = null
    flash('项目已删除')
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '删除失败')
  } finally {
    busy.value = false
  }
}

async function saveScriptText() {
  if (!detail.value) return
  busy.value = true
  try {
    const res = await updateProject(detail.value.id, { script: detail.value.script })
    detail.value = { ...detail.value, ...res.data }
    flash('口播稿已保存')
  } catch (e: any) {
    error.value = msg(e, '保存失败')
  } finally {
    busy.value = false
  }
}

async function submitAvatar() {
  if (!avatarForm.name.trim()) {
    error.value = '形象名称必填'
    return
  }
  busy.value = true
  try {
    await createAvatar({ ...avatarForm, name: avatarForm.name.trim() })
    flash('形象已创建')
    Object.assign(avatarForm, { name: '', style: '', preview_url: '', remark: '' })
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '创建形象失败')
  } finally {
    busy.value = false
  }
}

async function removeAvatar(row: DhAvatar) {
  if (!window.confirm(`确认删除形象「${row.name}」？`)) return
  try {
    await deleteAvatar(row.id)
    flash('形象已删除')
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '删除失败')
  }
}

async function submitVoice() {
  if (!voiceForm.name.trim()) {
    error.value = '音色名称必填'
    return
  }
  busy.value = true
  try {
    await createVoice({ ...voiceForm, name: voiceForm.name.trim() })
    flash('音色已创建')
    Object.assign(voiceForm, { name: '', voice_id: '', remark: '' })
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '创建音色失败')
  } finally {
    busy.value = false
  }
}

async function removeVoice(row: DhVoice) {
  if (!window.confirm(`确认删除音色「${row.name}」？`)) return
  try {
    await deleteVoice(row.id)
    flash('音色已删除')
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '删除失败')
  }
}

async function submitWorkflow() {
  if (!workflowForm.name.trim()) {
    error.value = '流程名称必填'
    return
  }
  busy.value = true
  try {
    await createWorkflow({
      name: workflowForm.name.trim(),
      description: workflowForm.description.trim(),
      steps: stepDraft.value,
    })
    flash('工作流已创建')
    Object.assign(workflowForm, { name: '', description: '', steps: [] })
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '创建失败')
  } finally {
    busy.value = false
  }
}

async function toggleWorkflow(row: DhWorkflow) {
  try {
    await updateWorkflow(row.id, { enabled: !row.enabled })
    flash(row.enabled ? '工作流已停用' : '工作流已启用')
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '更新失败')
  }
}

async function removeWorkflow(row: DhWorkflow) {
  if (!window.confirm(`确认删除工作流「${row.name}」？`)) return
  try {
    await deleteWorkflow(row.id)
    flash('工作流已删除')
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '删除失败')
  }
}

async function execWorkflow(row: DhWorkflow) {
  if (!workflowTarget.value) {
    error.value = '请先在上方选择要执行的项目'
    return
  }
  busy.value = true
  try {
    const res = await runWorkflow(row.id, { project_id: Number(workflowTarget.value) })
    flash(res.data.message ?? '工作流已执行')
    detail.value = res.data.project
    await loadAll()
  } catch (e: any) {
    error.value = msg(e, '执行失败')
  } finally {
    busy.value = false
  }
}

function statusClass(status: string): string {
  if (status === 'done') return 'ok'
  if (status === 'failed') return 'bad'
  if (status === 'rendering' || status === 'scripting') return 'warn'
  return ''
}

function taskClass(status: string): string {
  if (status === 'success') return 'ok'
  if (status === 'failed') return 'bad'
  if (status === 'running') return 'warn'
  return ''
}

function durationText(sec: number): string {
  if (!sec) return '-'
  const m = Math.floor(sec / 60)
  return m > 0 ? `${m} 分 ${sec % 60} 秒` : `${sec} 秒`
}

onMounted(loadAll)
</script>

<style scoped>
.dh-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 20px 60px;
  color: var(--color-text, #1f2329);
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.page-head h2 {
  margin: 0 0 6px;
  font-size: 22px;
}

.sub {
  margin: 0;
  font-size: 13px;
  color: var(--color-muted, #8a919f);
}

.banner {
  margin-bottom: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
}

.banner.ok {
  background: rgba(0, 180, 42, 0.1);
  color: #0a8a2a;
}

.banner.bad {
  background: rgba(245, 63, 63, 0.1);
  color: #c22b2b;
}

.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat {
  background: var(--color-card, #fff);
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 10px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stat .k {
  font-size: 12px;
  color: var(--color-muted, #8a919f);
}

.stat strong {
  font-size: 22px;
  line-height: 1.1;
}

.engines {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.eng {
  background: var(--color-card, #fff);
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 10px;
  padding: 14px;
}

.eng-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.eng-name {
  font-weight: 600;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.dot.on {
  background: #00b42a;
}

.dot.off {
  background: #f53f3f;
}

.eng-engine,
.eng-detail {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-muted, #8a919f);
}

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.tab {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid var(--color-border, #e5e6eb);
  background: var(--color-card, #fff);
  cursor: pointer;
  font-size: 14px;
  color: inherit;
}

.tab.active {
  background: var(--color-primary, #165dff);
  border-color: var(--color-primary, #165dff);
  color: #fff;
}

.card {
  background: var(--color-card, #fff);
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 12px;
  padding: 18px;
  margin-bottom: 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.card-head h3 {
  margin: 0;
  font-size: 16px;
}

.card-head h4 {
  margin: 0;
  font-size: 14px;
}

.hint,
.muted {
  font-size: 12px;
  color: var(--color-muted, #8a919f);
}

.actions {
  display: flex;
  gap: 8px;
}

.form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
}

.form.inline {
  margin-top: 14px;
}

.form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.form label > span {
  color: var(--color-muted, #8a919f);
}

.form input,
.form select,
.form textarea {
  padding: 8px 10px;
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 8px;
  font-size: 13px;
  background: var(--color-card, #fff);
  color: inherit;
  font-family: inherit;
}

.form input:focus,
.form select:focus,
.form textarea:focus {
  outline: none;
  border-color: var(--color-primary, #165dff);
}

.form .wide {
  grid-column: 1 / -1;
}

.form .check {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

.form-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.steps {
  grid-column: 1 / -1;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.step {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 14px;
  border: 1px dashed var(--color-border, #e5e6eb);
  border-radius: 8px;
  font-size: 13px;
}

.step-name {
  font-weight: 600;
}

.btn {
  border: 1px solid var(--color-border, #e5e6eb);
  background: var(--color-card, #fff);
  color: inherit;
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.primary {
  background: var(--color-primary, #165dff);
  border-color: var(--color-primary, #165dff);
  color: #fff;
}

.btn.ghost {
  background: transparent;
}

.btn.mini {
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 6px;
}

.btn.danger {
  color: #f53f3f;
  border-color: rgba(245, 63, 63, 0.4);
}

.btn.lg {
  padding: 10px 22px;
  font-size: 14px;
}

.filters {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.filters input,
.filters select {
  padding: 7px 10px;
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 8px;
  font-size: 13px;
  background: var(--color-card, #fff);
  color: inherit;
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.tbl th,
.tbl td {
  padding: 9px 10px;
  border-bottom: 1px solid var(--color-border, #e5e6eb);
  text-align: left;
  vertical-align: middle;
}

.tbl th {
  font-weight: 600;
  color: var(--color-muted, #8a919f);
  font-size: 12px;
}

.tbl tr.picked {
  background: rgba(22, 93, 255, 0.06);
}

.tbl .empty,
.empty {
  text-align: center;
  color: var(--color-muted, #8a919f);
  padding: 18px;
  font-size: 13px;
}

.ops {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

.strong {
  font-weight: 600;
}

.tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  background: rgba(138, 145, 159, 0.12);
  color: var(--color-muted, #8a919f);
}

.tag.ok {
  background: rgba(0, 180, 42, 0.12);
  color: #0a8a2a;
}

.tag.bad {
  background: rgba(245, 63, 63, 0.12);
  color: #c22b2b;
}

.tag.warn {
  background: rgba(255, 125, 0, 0.14);
  color: #b35f00;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 14px;
  font-size: 13px;
}

.pager > div {
  display: flex;
  gap: 6px;
}

.meta {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--color-muted, #8a919f);
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border, #e5e6eb);
}

.warn-text {
  color: #b35f00;
}

.bad-text {
  color: #c22b2b;
}

.script-panel {
  margin-top: 14px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.script-panel textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.7;
  resize: vertical;
  background: var(--color-card, #fff);
  color: inherit;
  font-family: inherit;
}

.segs {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.seg {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 10px;
}

.seg-idx {
  flex: 0 0 26px;
  height: 26px;
  border-radius: 50%;
  background: rgba(22, 93, 255, 0.12);
  color: var(--color-primary, #165dff);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.seg-body {
  flex: 1;
}

.seg-body p {
  margin: 6px 0;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.tile {
  border: 1px solid var(--color-border, #e5e6eb);
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tile img {
  width: 100%;
  height: 130px;
  object-fit: cover;
  border-radius: 8px;
}

.tile-name {
  font-weight: 600;
  font-size: 14px;
}

.tile-meta {
  font-size: 12px;
  color: var(--color-muted, #8a919f);
}

.tile-path {
  color: var(--color-muted, #8a919f);
  word-break: break-all;
}

.out {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 14px;
  font-size: 12px;
}

.out a {
  color: var(--color-primary, #165dff);
  word-break: break-all;
}

@media (max-width: 720px) {
  .dh-page {
    padding: 16px 12px 40px;
  }

  .form {
    grid-template-columns: 1fr;
  }

  .tbl {
    display: block;
    overflow-x: auto;
    white-space: nowrap;
  }
}
</style>
