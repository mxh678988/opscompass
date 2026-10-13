<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  askKnowledgeBase,
  createKnowledgeBase,
  deleteKnowledgeBase,
  deleteKnowledgeBaseFile,
  fetchKnowledgeBase,
  fetchKnowledgeBaseFiles,
  fetchKnowledgeBases,
  patchKnowledgeBase,
  uploadKnowledgeBaseFile,
  type KnowledgeAskOut,
  type KnowledgeBaseItem,
  type KnowledgeBasePatch,
} from '@/api/knowledge'

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
function fmtSize(n?: number) {
  if (n === null || n === undefined) return '-'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}

/* ---------- 知识库列表 ---------- */
const bases = ref<KnowledgeBaseItem[]>([])
const basesLoading = ref(false)
const keyword = ref('')
const statusFilter = ref('')

async function loadBases() {
  basesLoading.value = true
  try {
    const res = await fetchKnowledgeBases({
      keyword: keyword.value || undefined,
      status: statusFilter.value || undefined,
    })
    bases.value = res.data ?? []
  } catch (e) {
    tip('error', `知识库加载失败：${errText(e)}`)
  } finally {
    basesLoading.value = false
  }
}

/* ---------- 新建知识库 ---------- */
const showCreate = ref(false)
const createForm = reactive({ name: '', description: '' })
const creating = ref(false)

async function submitCreate() {
  if (!createForm.name.trim()) {
    tip('warn', '请填写知识库名称')
    return
  }
  creating.value = true
  try {
    await createKnowledgeBase({
      name: createForm.name.trim(),
      description: createForm.description.trim() || null,
    })
    tip('ok', `知识库「${createForm.name.trim()}」已创建`)
    showCreate.value = false
    createForm.name = ''
    createForm.description = ''
    await loadBases()
  } catch (e) {
    tip('error', `创建失败：${errText(e)}`)
  } finally {
    creating.value = false
  }
}

/* ---------- 库详情 / 文件 / 问答 ---------- */
const detail = ref<KnowledgeBaseItem | null>(null)
const detailLoading = ref(false)
const filesLoading = ref(false)
const askLoading = ref(false)
const askResult = ref<KnowledgeAskOut | null>(null)
const question = ref('')
const uploadInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const editForm = reactive<KnowledgeBasePatch>({ name: '', description: '', status: '' })
const showEdit = ref(false)

async function openDetail(base: KnowledgeBaseItem) {
  detail.value = base
  detailLoading.value = true
  askResult.value = null
  question.value = ''
  try {
    const res = await fetchKnowledgeBase(base.id)
    detail.value = res.data
    editForm.name = res.data?.name ?? ''
    editForm.description = res.data?.description ?? ''
    editForm.status = res.data?.status ?? 'active'
  } catch (e) {
    tip('error', `详情加载失败：${errText(e)}`)
  } finally {
    detailLoading.value = false
  }
}

async function loadFiles() {
  if (!detail.value) return
  filesLoading.value = true
  try {
    const res = await fetchKnowledgeBaseFiles(detail.value.id)
    if (detail.value) detail.value.files = res.data ?? []
  } catch (e) {
    tip('error', `文件列表加载失败：${errText(e)}`)
  } finally {
    filesLoading.value = false
  }
}

async function onUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !detail.value) return
  uploading.value = true
  try {
    await uploadKnowledgeBaseFile(detail.value.id, file)
    tip('ok', `文件「${file.name}」已上传`)
    await loadFiles()
  } catch (err) {
    tip('error', `上传失败：${errText(err)}`)
  } finally {
    uploading.value = false
    if (uploadInput.value) uploadInput.value.value = ''
  }
}

async function removeFile(f: { id: number }) {
  if (!detail.value) return
  try {
    await deleteKnowledgeBaseFile(f.id, detail.value.id)
    tip('ok', '文件已删除')
    await loadFiles()
  } catch (e) {
    tip('error', `删除失败：${errText(e)}`)
  }
}

async function ask() {
  if (!detail.value) return
  const q = question.value.trim()
  if (!q) {
    tip('warn', '请先输入问题')
    return
  }
  askLoading.value = true
  try {
    const res = await askKnowledgeBase(detail.value.id, { question: q, top_k: 5 })
    askResult.value = res.data
  } catch (e) {
    tip('error', `问答失败：${errText(e)}`)
  } finally {
    askLoading.value = false
  }
}

async function saveEdit() {
  if (!detail.value) return
  if (!editForm.name?.trim()) {
    tip('warn', '知识库名称不能为空')
    return
  }
  try {
    await patchKnowledgeBase(detail.value.id, {
      name: editForm.name?.trim(),
      description: editForm.description || null,
      status: editForm.status,
    })
    tip('ok', '知识库已更新')
    showEdit.value = false
    await loadBases()
    await openDetail(detail.value)
  } catch (e) {
    tip('error', `更新失败：${errText(e)}`)
  }
}

async function removeBase(base: KnowledgeBaseItem) {
  if (!window.confirm(`确认删除知识库「${base.name}」？删除后不可恢复。`)) return
  try {
    await deleteKnowledgeBase(base.id)
    tip('ok', '知识库已删除')
    if (detail.value?.id === base.id) detail.value = null
    await loadBases()
  } catch (e) {
    tip('error', `删除失败：${errText(e)}`)
  }
}

onMounted(loadBases)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>知识中心</h2>
        <p class="page-desc">知识库总览 / 文件管理 / 库内问答，沉淀企业运营知识并支撑 Agent 检索引用</p>
      </div>
      <button class="btn primary" @click="showCreate = true">新建知识库</button>
    </div>

    <div v-if="msg.text" class="msg" :class="`msg-${msg.type}`">{{ msg.text }}</div>

    <div class="card">
      <div class="card-head">
        <h3>知识库列表</h3>
        <div class="head-ops">
          <select v-model="statusFilter" class="input select" @change="loadBases">
            <option value="">全部状态</option>
            <option value="active">生效中</option>
            <option value="disabled">已停用</option>
          </select>
          <div class="search-row">
            <input v-model="keyword" class="input grow" placeholder="按名称搜索" @keyup.enter="loadBases" />
            <button class="btn" @click="loadBases">搜索</button>
            <button v-if="keyword || statusFilter" class="btn ghost" @click="keyword = ''; statusFilter = ''; loadBases()">清除</button>
          </div>
        </div>
      </div>
      <div v-if="basesLoading" class="loading">加载中…</div>
      <div v-else-if="!bases.length" class="empty">
        <p class="empty-title">暂无知识库</p>
        <p class="empty-sub">点击右上角「新建知识库」开始沉淀团队知识</p>
      </div>
      <table v-else class="table">
        <thead><tr><th>名称</th><th>描述</th><th>文档</th><th>文件</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="b in bases" :key="b.id">
            <td class="td-main">{{ b.name }}</td>
            <td class="td-muted">{{ b.description || '-' }}</td>
            <td>{{ b.doc_count ?? 0 }}</td>
            <td>{{ b.file_count ?? 0 }}</td>
            <td><span class="badge" :class="b.status === 'active' ? 'ok' : 'muted'">{{ b.status === 'active' ? '生效中' : '已停用' }}</span></td>
            <td class="td-muted">{{ dt(b.created_at) }}</td>
            <td class="ops">
              <button class="btn ghost sm" @click="openDetail(b)">管理</button>
              <button class="btn ghost sm danger-text" @click="removeBase(b)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ============ 新建知识库弹层 ============ -->
    <div v-if="showCreate" class="mask" @click.self="showCreate = false">
      <div class="drawer">
        <div class="drawer-head">
          <div class="drawer-title"><h3>新建知识库</h3></div>
          <button class="btn ghost sm" @click="showCreate = false">关闭</button>
        </div>
        <form class="form" @submit.prevent="submitCreate">
          <div class="field">
            <label>知识库名称 <em>*</em></label>
            <input v-model="createForm.name" class="input" placeholder="例如：运营 SOP 库" required />
          </div>
          <div class="field">
            <label>描述</label>
            <textarea v-model="createForm.description" class="input area" rows="3" placeholder="这个知识库用来沉淀什么内容"></textarea>
          </div>
          <button class="btn primary block" type="submit" :disabled="creating">
            {{ creating ? '创建中…' : '创建知识库' }}
          </button>
        </form>
      </div>
    </div>

    <!-- ============ 知识库管理弹层 ============ -->
    <div v-if="detail" class="mask" @click.self="detail = null">
      <div class="drawer wide">
        <div class="drawer-head">
          <div class="drawer-title">
            <h3>{{ detail.name }}</h3>
            <span class="badge" :class="detail.status === 'active' ? 'ok' : 'muted'">{{ detail.status === 'active' ? '生效中' : '已停用' }}</span>
          </div>
          <div class="drawer-ops">
            <button class="btn ghost sm" @click="showEdit = !showEdit">{{ showEdit ? '收起编辑' : '编辑' }}</button>
            <button class="btn ghost sm" @click="detail = null">关闭</button>
          </div>
        </div>

        <div v-if="detailLoading" class="loading">加载中…</div>
        <template v-else>
          <div v-if="showEdit" class="card">
            <div class="card-head"><h3>编辑知识库</h3></div>
            <form class="form" @submit.prevent="saveEdit">
              <div class="field">
                <label>名称 <em>*</em></label>
                <input v-model="editForm.name" class="input" required />
              </div>
              <div class="field">
                <label>描述</label>
                <textarea v-model="editForm.description" class="input area" rows="2"></textarea>
              </div>
              <div class="field">
                <label>状态</label>
                <select v-model="editForm.status" class="input select">
                  <option value="active">生效中</option>
                  <option value="disabled">已停用</option>
                </select>
              </div>
              <button class="btn primary" type="submit">保存修改</button>
            </form>
          </div>

          <p v-if="detail.description" class="meta-line">{{ detail.description }}</p>
          <p class="meta-line">创建于 {{ dt(detail.created_at) }} · 文档 {{ detail.doc_count ?? 0 }} 篇 · 文件 {{ (detail.files ?? []).length }} 个</p>

          <div class="card">
            <div class="card-head">
              <h3>库内文件</h3>
              <div class="head-ops">
                <input ref="uploadInput" type="file" class="file-input" @change="onUpload" />
                <button class="btn sm" :disabled="uploading" @click="uploadInput?.click()">
                  {{ uploading ? '上传中…' : '上传文件' }}
                </button>
                <button class="btn ghost sm" @click="loadFiles">刷新</button>
              </div>
            </div>
            <div v-if="filesLoading" class="loading">加载中…</div>
            <div v-else-if="!(detail.files ?? []).length" class="empty sm">
              <p class="empty-title">暂无文件</p>
              <p class="empty-sub">上传 txt / md / csv / json 等文本文件后即可参与库内问答</p>
            </div>
            <table v-else class="table">
              <thead><tr><th>文件名</th><th>类型</th><th>大小</th><th>上传者</th><th>上传时间</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="f in detail.files" :key="f.id">
                  <td class="td-main">{{ f.file_name }}</td>
                  <td><span class="tag">{{ f.file_type }}</span></td>
                  <td class="td-muted">{{ fmtSize(f.size_bytes) }}</td>
                  <td class="td-muted">{{ f.uploader || '-' }}</td>
                  <td class="td-muted">{{ dt(f.created_at) }}</td>
                  <td class="ops">
                    <button class="btn ghost sm danger-text" @click="removeFile(f)">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="card">
            <div class="card-head"><h3>库内问答</h3></div>
            <div class="qa-row">
              <input v-model="question" class="input grow" placeholder="向知识库提问，例如：我们沉淀过哪些促销复盘结论？" @keyup.enter="ask" />
              <button class="btn primary" :disabled="askLoading" @click="ask">{{ askLoading ? '思考中…' : '提问' }}</button>
            </div>
            <div v-if="askResult" class="qa-result">
              <p class="plain">{{ askResult.answer }}</p>
              <p v-if="askResult.fallback" class="hint">模型不可用，当前为片段降级回答</p>
              <p v-else-if="askResult.model" class="hint">模型：{{ askResult.model }}</p>
              <div v-if="askResult.sources.length" class="chip-wrap">
                <span v-for="(s, i) in askResult.sources" :key="i" class="chip">{{ s.title }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: var(--space-4); }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); }
.page-head h2 { margin: 0; font-size: 20px; }
.page-desc { margin: var(--space-1) 0 0; font-size: 13px; color: var(--color-text-muted); }
.msg {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: 13px;
}
.msg-ok { background: var(--color-success-light); color: var(--color-success); }
.msg-warn { background: var(--color-warning-light); color: var(--color-warning); }
.msg-error { background: var(--color-error-light); color: var(--color-error); }
.card { display: flex; flex-direction: column; gap: var(--space-3); }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.card-head h3 { margin: 0; font-size: 16px; }
.head-ops { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.search-row { display: flex; gap: var(--space-2); min-width: 260px; max-width: 420px; }
.select { width: auto; }
.file-input { display: none; }
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
.table { width: 100%; }
.td-main { font-weight: 500; }
.td-muted { color: var(--color-text-muted); font-size: 12px; }
.ops { display: flex; gap: var(--space-1); white-space: nowrap; }
.danger-text { color: var(--color-error); }
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
.badge.muted { background: var(--color-bg-subtle); color: var(--color-text-muted); }
.tag {
  display: inline-block;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  background: var(--color-primary-light);
  color: var(--color-primary);
}
.meta-line { margin: 0; font-size: 13px; color: var(--color-text-muted); }
.form { display: flex; flex-direction: column; gap: var(--space-4); }
.field { display: flex; flex-direction: column; gap: var(--space-1); }
.field label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.field label em { color: var(--color-error); font-style: normal; }
.input { width: 100%; }
.input.area { resize: vertical; }
.qa-row { display: flex; gap: var(--space-2); }
.qa-result {
  padding: var(--space-4);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.plain { margin: 0; white-space: pre-wrap; color: var(--color-text-secondary); font-size: 13px; }
.hint { margin: 0; font-size: 12px; color: var(--color-text-muted); }
.chip-wrap { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.chip {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-size: 12px;
}
.mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
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
.drawer.wide { width: min(820px, 96vw); }
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
</style>
