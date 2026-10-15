<template>
  <div class="sentiment-page">
    <!-- 页面头 -->
    <div class="page-head">
      <div>
        <h2>舆情监控</h2>
        <p class="sub">插件情报中枢 · 监测主题与情感分析</p>
      </div>
      <div class="head-actions">
        <span class="badge">plugin: sentiment</span>
        <span class="badge">v0.12.0</span>
        <span class="badge">ns: com.laomeng.opp.ner</span>
        <button class="btn ghost" @click="loadTopics" :disabled="loading">
          {{ loading ? '加载中…' : '刷新' }}
        </button>
        <button class="btn primary" @click="showForm = !showForm">创建主题</button>
      </div>
    </div>

    <!-- 消息提示 -->
    <div v-if="msg.text" :class="['msg', msg.type]">{{ msg.text }}</div>

    <!-- 创建表单 -->
    <div v-if="showForm" class="create-card">
      <div class="form-row">
        <input
          v-model="form.name"
          class="field"
          placeholder="主题名称，如：品牌舆情"
          @keyup.enter="createTopic"
        />
        <input
          v-model="form.keywords"
          class="field grow"
          placeholder="关键词，逗号分隔，如：AI, 运营"
          @keyup.enter="createTopic"
        />
        <button class="btn primary" @click="createTopic" :disabled="saving">
          {{ saving ? '创建中…' : '创建' }}
        </button>
        <button class="btn ghost" @click="showForm = false">取消</button>
      </div>
    </div>

    <!-- 监测主题 -->
    <div class="section">
      <div class="section-head">
        <h3>监测主题 <small>{{ topics.length }} 个</small></h3>
        <span class="hint">点击主题卡片查看分析报告</span>
      </div>
      <div v-if="topics.length" class="topic-grid">
        <div
          v-for="t in topics"
          :key="t.id"
          class="topic-card"
          :class="{ active: selectedId === t.id }"
          @click="selectTopic(t)"
        >
          <div class="topic-head">
            <strong>{{ t.name }}</strong>
            <button class="del" title="删除主题" @click.stop="removeTopic(t.id)">删除</button>
          </div>
          <div class="chips">
            <span v-for="k in t.keywords" :key="k" class="chip">{{ k }}</span>
          </div>
          <div class="topic-meta">
            <span class="status">{{ t.status }}</span>
            <span>{{ formatDate(t.created_at) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="empty">暂无监测主题，点击右上角「创建主题」开始监测</div>
    </div>

    <!-- 分析报告 -->
    <div v-if="analytics" class="section">
      <div class="section-head">
        <h3>分析报告 <small>近 7 日</small></h3>
        <span class="hint">{{ formatDate(analytics.hot_heat?.start_date) }} ~ {{ formatDate(analytics.hot_heat?.end_date) }}</span>
      </div>
      <div class="stats">
        <div class="stat">
          <span class="label">监测条数</span>
          <strong>{{ analytics.hot_heat?.total_items ?? 0 }}</strong>
          <em>总采集量</em>
        </div>
        <div class="stat">
          <span class="label">正面</span>
          <strong class="pos">{{ analytics.emotion?.positive ?? 0 }}</strong>
          <em>{{ ratio('positive') }}%</em>
        </div>
        <div class="stat">
          <span class="label">中性</span>
          <strong class="neu">{{ analytics.emotion?.neutral ?? 0 }}</strong>
          <em>{{ ratio('neutral') }}%</em>
        </div>
        <div class="stat">
          <span class="label">负面</span>
          <strong class="neg">{{ analytics.emotion?.negative ?? 0 }}</strong>
          <em>{{ ratio('negative') }}%</em>
        </div>
      </div>
      <div class="bar">
        <div class="bar-pos" :style="{ width: ratio('positive') + '%' }"></div>
        <div class="bar-neu" :style="{ width: ratio('neutral') + '%' }"></div>
        <div class="bar-neg" :style="{ width: ratio('negative') + '%' }"></div>
      </div>
      <div class="legend">
        <span><i class="dot pos"></i>正面</span>
        <span><i class="dot neu"></i>中性</span>
        <span><i class="dot neg"></i>负面</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

interface TopicItem {
  id: string
  name: string
  keywords: string[]
  status: string
  created_at: string
}

interface AnalyticsOut {
  topic_id: string
  hot_heat?: { total_items: number; start_date: string; end_date: string }
  emotion?: { positive: number; neutral: number; negative: number; total: number }
}

const pluginId = 'sentiment'

const topics = ref<TopicItem[]>([])
const analytics = ref<AnalyticsOut | null>(null)
const selectedId = ref<string | null>(null)
const loading = ref(false)
const saving = ref(false)
const showForm = ref(false)
const form = reactive({ name: '', keywords: '' })
const msg = reactive({ type: '', text: '' })

const call = async (action: string, params: Record<string, unknown> = {}) => {
  const result = await (window as any).opsCompass?.send?.({ plugin_id: pluginId, action, params })
  return result
}

const loadTopics = async () => {
  loading.value = true
  msg.type = ''
  msg.text = ''
  try {
    const result = await call('list_topics')
    const data = result && result.data !== undefined ? result.data : result
    topics.value = Array.isArray(data) ? (data as TopicItem[]) : []
    if (topics.value.length) {
      selectTopic(topics.value[0])
    } else {
      analytics.value = null
      selectedId.value = null
    }
  } catch (e) {
    msg.type = 'bad'
    msg.text = '加载主题失败：' + ((e as Error).message || String(e))
  } finally {
    loading.value = false
  }
}

const createTopic = async () => {
  const name = form.name.trim()
  if (!name) {
    msg.type = 'bad'
    msg.text = '请填写主题名称'
    return
  }
  const keywords = form.keywords
    .split(/[,，]/)
    .map((s: string) => s.trim())
    .filter(Boolean)
  saving.value = true
  try {
    await call('create_topic', { name, keywords })
    form.name = ''
    form.keywords = ''
    showForm.value = false
    msg.type = 'ok'
    msg.text = '主题创建成功'
    await loadTopics()
  } catch (e) {
    msg.type = 'bad'
    msg.text = '创建失败：' + ((e as Error).message || String(e))
  } finally {
    saving.value = false
  }
}

const removeTopic = async (id: string) => {
  if (!window.confirm('确认删除该监测主题？')) return
  try {
    await call('delete_topic', { topic_id: id })
    msg.type = 'ok'
    msg.text = '主题已删除'
    await loadTopics()
  } catch (e) {
    msg.type = 'bad'
    msg.text = '删除失败：' + ((e as Error).message || String(e))
  }
}

const selectTopic = async (t: TopicItem) => {
  selectedId.value = t.id
  try {
    const result = await call('get_analytics', { topic_id: t.id, period: '7d' })
    const data = result && result.data !== undefined ? result.data : result
    analytics.value = data && data.emotion ? (data as AnalyticsOut) : null
  } catch (e) {
    analytics.value = null
  }
}

const ratio = (key: string) => {
  const emotion = analytics.value?.emotion
  const total = emotion?.total || 0
  if (!total) return 0
  return Math.round(((emotion?.[key as 'positive'] || 0) / total) * 100)
}

const formatDate = (s?: string) => (s ? String(s).slice(0, 10) : '')

onMounted(loadTopics)
</script>

<style scoped>
.sentiment-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 20px 60px;
}

/* 页面头 */
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.page-head h2 {
  margin: 0 0 6px;
  font-size: 22px;
  color: var(--color-text);
}
.sub {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-muted);
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.badge {
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  background: var(--color-bg-subtle);
}

/* 按钮 */
.btn {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  font-size: 13px;
  transition: background var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.btn.primary {
  background: var(--color-primary);
  color: var(--color-text-on-primary);
}
.btn.primary:hover {
  background: var(--color-primary-hover);
}
.btn.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn.ghost {
  background: var(--color-bg);
  border-color: var(--color-border);
  color: var(--color-text-secondary);
}
.btn.ghost:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-primary-border);
  color: var(--color-primary);
}

/* 消息 */
.msg {
  margin: 0 0 14px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
}
.msg.ok {
  background: var(--color-success-light);
  color: var(--color-success);
  border: 1px solid var(--color-success-border);
}
.msg.bad {
  background: var(--color-error-light);
  color: var(--color-error);
  border: 1px solid var(--color-error-border);
}

/* 创建表单 */
.create-card {
  background: var(--color-bg);
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: 16px;
  margin-bottom: 20px;
}
.form-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.field {
  flex: 1 1 200px;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.field:focus {
  border-color: var(--color-focus);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}
.field.grow {
  flex: 2 1 260px;
}

/* 区块 */
.section {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  padding: 18px;
  margin-bottom: 20px;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.section h3 {
  margin: 0;
  font-size: 16px;
  color: var(--color-text);
}
.section h3 small {
  margin-left: 8px;
  font-weight: 400;
  font-size: 12px;
  color: var(--color-text-muted);
}
.hint {
  font-size: 12px;
  color: var(--color-text-muted);
}

/* 主题卡片 */
.topic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}
.topic-card {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  cursor: pointer;
  transition: border-color var(--transition-base), box-shadow var(--transition-base), transform var(--transition-base);
}
.topic-card:hover {
  border-color: var(--color-primary-border);
  box-shadow: var(--shadow-card);
  transform: translateY(-1px);
}
.topic-card.active {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
  box-shadow: var(--shadow-card);
}
.topic-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.topic-head strong {
  font-size: 15px;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.del {
  flex: 0 0 auto;
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 12px;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast), background var(--transition-fast);
}
.del:hover {
  color: var(--color-error);
  background: var(--color-error-light);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.chip {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--color-primary-light);
  color: var(--color-primary);
  border: 1px solid var(--color-primary-border);
}
.topic-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--color-text-muted);
}
.topic-meta .status {
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

/* 空态 */
.empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--color-text-muted);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
  font-size: 13px;
}

/* 统计 */
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
.stat {
  background: var(--color-bg-subtle);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat .label {
  font-size: 12px;
  color: var(--color-text-muted);
}
.stat strong {
  font-size: 24px;
  line-height: 1.1;
  color: var(--color-text);
}
.stat strong.pos {
  color: var(--color-success);
}
.stat strong.neu {
  color: var(--color-warning);
}
.stat strong.neg {
  color: var(--color-error);
}
.stat em {
  font-style: normal;
  font-size: 12px;
  color: var(--color-text-muted);
}

/* 情绪占比条 */
.bar {
  display: flex;
  height: 10px;
  border-radius: var(--radius-full);
  overflow: hidden;
  background: var(--color-bg-hover);
  margin-bottom: 10px;
}
.bar-pos {
  background: var(--color-success);
  transition: width var(--transition-slow);
}
.bar-neu {
  background: var(--color-warning);
  transition: width var(--transition-slow);
}
.bar-neg {
  background: var(--color-error);
  transition: width var(--transition-slow);
}
.legend {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  margin-right: 6px;
  vertical-align: -1px;
}
.dot.pos {
  background: var(--color-success);
}
.dot.neu {
  background: var(--color-warning);
}
.dot.neg {
  background: var(--color-error);
}
</style>
