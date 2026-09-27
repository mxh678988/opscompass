<script setup lang="ts">
// 存储适配层运维台：引擎总览 / 路由识别 / 全文检索 / 一致性对账 / 运维动作
import { computed, onMounted, reactive, ref } from 'vue'
import {
  backfillTimeseries,
  bootstrapStorage,
  fetchRecentConsistency,
  fetchRoutingRules,
  fetchStorageOverview,
  identifyRoute,
  reindexDocuments,
  runConsistency,
  searchDocuments,
  type ConsistencyRecord,
  type ConsistencyRun,
  type IdentifyResult,
  type RoutingRules,
  type SearchOut,
  type StorageOverview,
} from '@/api/storage'

const KIND_LABEL: Record<string, string> = {
  relational: '关系型',
  timeseries: '时序',
  fulltext: '全文',
  cache: '缓存',
  file: '文件',
}

const overview = ref<StorageOverview | null>(null)
const routing = ref<RoutingRules | null>(null)
const records = ref<ConsistencyRecord[]>([])
const loading = ref(false)
const error = ref('')
const notice = ref('')
const busy = ref('')

/** ---------------------------------------------------------- 识别试验台 */
const identifyForm = reactive({ ds_type: '', file_ext: '', content: '' })
const identifyResult = ref<IdentifyResult | null>(null)
const identifying = ref(false)

/** ---------------------------------------------------------- 全文检索 */
const searchForm = reactive({ q: '', doc_type: '', limit: 20 })
const searchResult = ref<SearchOut | null>(null)
const searching = ref(false)

/** ---------------------------------------------------------- 一致性对账 */
const SCOPE_LABEL: Record<string, string> = {
  metric_ts: '指标-时序',
  search_index: '检索索引',
  files: '文件',
}
const consistencyForm = reactive({ scopes: ['metric_ts', 'search_index', 'files'] as string[], auto_repair: false })
const consistencyResult = ref<ConsistencyRun | null>(null)
const reconciling = ref(false)

const healthyText = computed(() => {
  if (!overview.value) return '-'
  return overview.value.healthy ? '全部引擎可用' : '存在降级引擎'
})

function statEntries(kind: string) {
  const stats = overview.value?.stats?.[kind]
  if (!stats || typeof stats !== 'object') return [] as { k: string; v: string }[]
  return Object.entries(stats)
    .slice(0, 6)
    .map(([k, v]) => ({
      k,
      v: v !== null && typeof v === 'object' ? JSON.stringify(v).slice(0, 80) : String(v ?? '-'),
    }))
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [ov, rt, rec] = await Promise.all([
      fetchStorageOverview(),
      fetchRoutingRules(),
      fetchRecentConsistency(10),
    ])
    overview.value = ov.data
    routing.value = rt.data
    records.value = rec.data ?? []
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '加载失败'
  } finally {
    loading.value = false
  }
}

async function doIdentify() {
  identifying.value = true
  error.value = ''
  try {
    const res = await identifyRoute({
      ds_type: identifyForm.ds_type || undefined,
      file_ext: identifyForm.file_ext || undefined,
      content: identifyForm.content || undefined,
    })
    identifyResult.value = res.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '识别失败'
  } finally {
    identifying.value = false
  }
}

async function doSearch() {
  if (!searchForm.q.trim()) {
    error.value = '请输入检索关键词'
    return
  }
  searching.value = true
  error.value = ''
  try {
    const res = await searchDocuments({
      q: searchForm.q.trim(),
      doc_type: searchForm.doc_type || undefined,
      limit: Number(searchForm.limit) || 20,
    })
    searchResult.value = res.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '检索失败'
  } finally {
    searching.value = false
  }
}

async function doConsistency() {
  reconciling.value = true
  error.value = ''
  consistencyResult.value = null
  try {
    const res = await runConsistency({
      scopes: consistencyForm.scopes.length ? consistencyForm.scopes : undefined,
      auto_repair: consistencyForm.auto_repair,
    })
    consistencyResult.value = res.data
    const rec = await fetchRecentConsistency(10)
    records.value = rec.data ?? []
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '对账失败'
  } finally {
    reconciling.value = false
  }
}

async function runAction(name: string, fn: () => Promise<any>, tip: string) {
  busy.value = name
  error.value = ''
  notice.value = ''
  try {
    await fn()
    notice.value = tip
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '执行失败'
  } finally {
    busy.value = ''
  }
}

function scopeStatusClass(status: string) {
  if (status === 'passed') return 'ok'
  if (status === 'failed') return 'bad'
  if (status === 'skipped') return 'muted'
  return 'warn'
}

onMounted(load)
</script>

<template>
  <main class="storage">
    <header class="head">
      <h1>存储适配</h1>
      <p class="subtitle">
        统一调度关系型 / 时序 / 全文 / 缓存 / 文件五类引擎：按数据类型自动路由，支持全文检索与跨存储一致性对账
      </p>
    </header>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="notice" class="notice">{{ notice }}</p>

    <!-- 总览 -->
    <section class="panel">
      <div class="panel-head">
        <h2>引擎总览</h2>
        <div class="ops">
          <button
            :disabled="busy === 'bootstrap'"
            @click="runAction('bootstrap', bootstrapStorage, '初始化完成：受管目录 / 内置规则 / 时序分区已就绪')"
          >
            {{ busy === 'bootstrap' ? '初始化中…' : '初始化适配层' }}
          </button>
          <button
            :disabled="busy === 'backfill'"
            @click="runAction('backfill', () => backfillTimeseries(), '存量指标值已回填到时序分区表（幂等）')"
          >
            {{ busy === 'backfill' ? '回填中…' : '回填存量指标' }}
          </button>
          <button
            :disabled="busy === 'reindex'"
            @click="runAction('reindex', () => reindexDocuments(), '全文索引已重建')"
          >
            {{ busy === 'reindex' ? '重建中…' : '重建全文索引' }}
          </button>
        </div>
      </div>

      <div class="metrics">
        <div class="metric">
          <span class="label">适配层状态</span>
          <strong :class="overview?.healthy ? 'ok-text' : 'warn-text'">{{ healthyText }}</strong>
        </div>
        <div class="metric">
          <span class="label">类型路由</span>
          <strong>{{ overview?.storage_routing_enabled ? '已开启' : '已关闭' }}</strong>
        </div>
        <div class="metric">
          <span class="label">热点缓存</span>
          <strong>{{ overview?.cache_enabled ? '已开启' : '已关闭' }}</strong>
        </div>
        <div class="metric">
          <span class="label">路由规则</span>
          <strong>{{ routing?.rule_count ?? 0 }} 条（自定义 {{ routing?.custom_rule_count ?? 0 }}）</strong>
        </div>
      </div>

      <div class="engines">
        <div v-for="cap in overview?.capabilities ?? []" :key="cap.kind" class="engine">
          <div class="engine-head">
            <span class="kind">{{ KIND_LABEL[cap.kind] ?? cap.kind }}</span>
            <span class="tag" :class="cap.available ? (cap.degraded ? 'warn' : 'ok') : 'bad'">
              {{ cap.available ? (cap.degraded ? '降级' : '可用') : '不可用' }}
            </span>
          </div>
          <p class="engine-name">{{ cap.label }}<span class="mono"> / {{ cap.engine }}</span></p>
          <ul class="stats">
            <li v-for="item in statEntries(cap.kind)" :key="item.k">
              <span>{{ item.k }}</span><em>{{ item.v }}</em>
            </li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 路由识别 -->
    <section class="panel">
      <h2>类型路由与识别</h2>
      <p class="hint">按数据源类型、文件后缀、内容特征识别接入数据类型，并给出目标存储引擎。</p>
      <div class="form">
        <label>
          <span>数据源类型</span>
          <input v-model="identifyForm.ds_type" placeholder="如 mysql / clickhouse / redis" />
        </label>
        <label>
          <span>文件后缀</span>
          <input v-model="identifyForm.file_ext" placeholder="如 csv / pdf / png" />
        </label>
        <label class="wide">
          <span>内容特征</span>
          <input v-model="identifyForm.content" placeholder="如 门店日报，含 stat_time 时间序列字段" />
        </label>
        <button class="primary" :disabled="identifying" @click="doIdentify">
          {{ identifying ? '识别中…' : '识别路由' }}
        </button>
      </div>

      <div v-if="identifyResult" class="result">
        <span class="tag" :class="identifyResult.matched ? 'ok' : 'muted'">
          {{ identifyResult.matched ? '命中规则' : '未命中规则' }}
        </span>
        <strong>{{ KIND_LABEL[identifyResult.data_kind] ?? identifyResult.data_kind }}</strong>
        <span class="mono">→ {{ identifyResult.engine }}</span>
        <span class="reason">{{ identifyResult.reason }}</span>
      </div>

      <p class="by-kind">
        <span v-for="(cnt, kind) in routing?.by_kind ?? {}" :key="kind" class="chip">
          {{ KIND_LABEL[kind] ?? kind }} · {{ cnt }}
        </span>
      </p>

      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>规则</th>
            <th>匹配字段</th>
            <th>匹配值</th>
            <th>数据类型</th>
            <th>引擎</th>
            <th>优先级</th>
            <th>范围</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rule in routing?.rules ?? []" :key="rule.id">
            <td>{{ rule.name }}</td>
            <td class="mono">{{ rule.match_field }}</td>
            <td class="mono ellipsis">{{ rule.match_value }}</td>
            <td>{{ KIND_LABEL[rule.data_kind] ?? rule.data_kind }}</td>
            <td class="mono">{{ rule.engine }}</td>
            <td>{{ rule.priority }}</td>
            <td>{{ rule.tenant_id ? '自定义' : '内置' }}</td>
            <td>
              <span class="tag" :class="rule.enabled ? 'ok' : 'muted'">{{ rule.enabled ? '启用' : '停用' }}</span>
            </td>
          </tr>
          <tr v-if="!(routing?.rules ?? []).length && !loading">
            <td colspan="8" class="empty">暂无规则，可点击「初始化适配层」写入内置规则</td>
          </tr>
        </tbody>
      </table>
      </div>
      <p v-if="loading" class="hint">加载中…</p>
    </section>

    <!-- 全文检索 -->
    <section class="panel">
      <h2>全文检索</h2>
      <div class="form">
        <label class="wide">
          <span>关键词</span>
          <input v-model="searchForm.q" placeholder="如 营收 / 门店 / 渠道" @keyup.enter="doSearch" />
        </label>
        <label>
          <span>文档类型</span>
          <select v-model="searchForm.doc_type">
            <option value="">全部</option>
            <option value="metric">指标</option>
            <option value="datasource">数据源</option>
            <option value="category">分类</option>
          </select>
        </label>
        <label>
          <span>条数上限</span>
          <input v-model="searchForm.limit" type="number" min="1" max="200" />
        </label>
        <button class="primary" :disabled="searching" @click="doSearch">
          {{ searching ? '检索中…' : '检索' }}
        </button>
      </div>

      <p v-if="searchResult" class="hint">
        命中 {{ searchResult.total }} 条 · 引擎 {{ searchResult.engine }}
        <template v-if="searchResult.note"> · {{ searchResult.note }}</template>
      </p>
      <ul v-if="searchResult?.items?.length" class="hits">
        <li v-for="hit in searchResult.items" :key="`${hit.doc_type}-${hit.doc_id}`">
          <div class="hit-head">
            <strong>{{ hit.title || hit.doc_id }}</strong>
            <span class="chip">{{ hit.doc_type }}</span>
            <span class="chip mono">{{ hit.doc_id }}</span>
          </div>
          <p v-if="hit.content" class="hit-body">{{ hit.content.slice(0, 160) }}</p>
        </li>
      </ul>
      <p v-else-if="searchResult" class="empty">无命中结果</p>
    </section>

    <!-- 一致性对账 -->
    <section class="panel">
      <h2>跨存储一致性对账</h2>
      <div class="form">
        <div class="checks">
          <label v-for="(label, scope) in SCOPE_LABEL" :key="scope" class="check">
            <input v-model="consistencyForm.scopes" type="checkbox" :value="scope" />
            <span>{{ label }}</span>
          </label>
        </div>
        <label class="check">
          <input v-model="consistencyForm.auto_repair" type="checkbox" />
          <span>自动修复差异</span>
        </label>
        <button class="primary" :disabled="reconciling" @click="doConsistency">
          {{ reconciling ? '对账中…' : '执行对账' }}
        </button>
      </div>

      <div v-if="consistencyResult" class="summary">
        <span class="tag" :class="scopeStatusClass(consistencyResult.overall)">
          {{ consistencyResult.overall }}
        </span>
        <span>检查 {{ consistencyResult.checked }}</span>
        <span>一致 {{ consistencyResult.matched }}</span>
        <span>修复 {{ consistencyResult.repaired }}</span>
        <span>清理 {{ consistencyResult.pruned }}</span>
        <span class="mono">{{ consistencyResult.elapsed_ms }} ms</span>
      </div>

      <div class="table-scroll">
      <table v-if="consistencyResult?.results?.length">
        <thead>
          <tr>
            <th>范围</th>
            <th>状态</th>
            <th>检查</th>
            <th>一致</th>
            <th>缺失</th>
            <th>多余</th>
            <th>不一致</th>
            <th>修复</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in consistencyResult.results" :key="item.scope">
            <td>{{ SCOPE_LABEL[item.scope] ?? item.scope }}</td>
            <td><span class="tag" :class="scopeStatusClass(item.status)">{{ item.status }}</span></td>
            <td>{{ item.checked }}</td>
            <td>{{ item.matched }}</td>
            <td>{{ item.missing ?? 0 }}</td>
            <td>{{ item.extra ?? 0 }}</td>
            <td>{{ item.mismatched ?? 0 }}</td>
            <td>{{ item.repaired ?? 0 }}</td>
          </tr>
        </tbody>
      </table>
      </div>

      <h3 class="sub">最近对账记录</h3>
      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>范围</th>
            <th>状态</th>
            <th>检查</th>
            <th>一致</th>
            <th>修复</th>
            <th>操作人</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rec in records" :key="rec.id">
            <td>{{ rec.created_at ?? '-' }}</td>
            <td>{{ SCOPE_LABEL[rec.scope] ?? rec.scope }}</td>
            <td><span class="tag" :class="scopeStatusClass(rec.status)">{{ rec.status }}</span></td>
            <td>{{ rec.checked }}</td>
            <td>{{ rec.matched }}</td>
            <td>{{ rec.repaired ?? 0 }}</td>
            <td>{{ rec.operator ?? '-' }}</td>
          </tr>
          <tr v-if="!records.length">
            <td colspan="7" class="empty">暂无对账记录</td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>
  </main>
</template>

<style scoped>
.storage { padding: 32px; max-width: 1400px; margin: 0 auto; }
.subtitle { color: var(--color-text-secondary); margin-bottom: 24px; font-size: 14px; }
.panel { border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 20px; margin-bottom: 20px; background: var(--color-bg); }
.panel h2 { font-size: 15px; font-weight: 600; color: var(--color-text); margin: 0 0 14px; }
.panel-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.sub { font-size: 14px; margin: 22px 0 10px; color: var(--color-text); }
/* minmax 使用 min(100%, X)：窄于 X 时列宽退化为 100%，避免栅格撑破面板 */
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr)); gap: 12px; margin-bottom: 18px; }
.metric { border: 1px solid var(--color-border-light); border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.metric .label { font-size: 12px; color: var(--color-text-secondary); }
.engines { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 230px), 1fr)); gap: 12px; }
.engine { border: 1px solid var(--color-border-light); border-radius: 8px; padding: 12px; min-width: 0; }
.engine-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-width: 0; }
.engine-head .kind { font-weight: 600; font-size: 14px; min-width: 0; overflow-wrap: anywhere; }
.engine-name { margin: 6px 0 8px; font-size: 12px; color: var(--color-text-secondary); min-width: 0; overflow-wrap: anywhere; word-break: break-word; }
.stats { list-style: none; margin: 0; padding: 0; font-size: 12px; }
.stats li { display: flex; justify-content: space-between; gap: 8px; color: var(--color-text-secondary); padding: 2px 0; min-width: 0; }
/* 长串 JSON / 路径 / URL 必须可断行，否则会撑破引擎卡片与面板 */
.stats em { font-style: normal; color: var(--color-text); min-width: 0; overflow-wrap: anywhere; word-break: break-all; text-align: right; }
.hit-body { min-width: 0; overflow-wrap: anywhere; word-break: break-word; }
.result .reason { min-width: 0; overflow-wrap: anywhere; word-break: break-word; }
.form { display: flex; flex-wrap: wrap; gap: 12px 16px; align-items: end; margin-bottom: 12px; }
.form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--color-text-secondary); min-width: 180px; }
.form label.wide { flex: 1; min-width: 260px; }
select, input { padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; width: 100%; box-sizing: border-box; }
button { padding: 8px 14px; border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-bg); cursor: pointer; font-size: 13px; }
button.primary { background: var(--color-primary); border-color: var(--color-primary); color: var(--color-bg); }
button.primary:disabled, button:disabled { opacity: 0.6; cursor: not-allowed; }
.ops { display: flex; gap: 8px; flex-wrap: wrap; }
table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 6px; }
th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--color-border-light); }
th { color: var(--color-text-secondary); font-weight: 500; white-space: nowrap; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.ellipsis { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; background: var(--color-bg-subtle); color: var(--color-text-muted); }
.tag.ok { background: var(--color-success-light); color: var(--color-success); }
.tag.warn { background: var(--color-warning-light); color: var(--color-warning); }
.tag.bad { background: var(--color-error-light); color: var(--color-error); }
.tag.muted { background: var(--color-bg-subtle); color: var(--color-text-muted); }
.chip { display: inline-block; padding: 2px 8px; border-radius: 10px; background: var(--color-primary-light); color: var(--color-primary); font-size: 12px; margin: 0 6px 6px 0; }
.result { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 13px; padding: 10px 12px; border: 1px solid var(--color-border-light); background: var(--color-bg-subtle); border-radius: 8px; }
.result .reason { color: var(--color-text-secondary); }
.by-kind { margin: 12px 0 4px; }
.hits { list-style: none; margin: 10px 0 0; padding: 0; }
.hits li { border: 1px solid var(--color-border-light); border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; }
.hit-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; }
.hit-body { margin: 6px 0 0; font-size: 12px; color: var(--color-text-secondary); }
.checks { display: flex; gap: 14px; flex-wrap: wrap; }
.check { flex-direction: row !important; align-items: center; gap: 6px !important; min-width: auto !important; }
.check input { width: auto; }
.summary { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; font-size: 13px; color: var(--color-text-secondary); margin-bottom: 10px; }
.ok-text { color: var(--color-success); }
.warn-text { color: var(--color-warning); }
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
    @media (max-width: 1024px) {
      .storage {
        padding: 20px 16px;
      }
    }
    @media (max-width: 768px) {
      .storage {
        padding: 16px 12px;
      }
      .panel {
        padding: 16px;
      }
      .metrics {
        grid-template-columns: repeat(auto-fit, minmax(min(100%, 140px), 1fr));
      }
      /* 小屏单列：配合 .engine { min-width: 0 } 保证卡片可收缩到容器宽度 */
      .engines {
        grid-template-columns: 1fr;
      }
      .form label,
      .form label.wide {
        min-width: 0;
        flex: 1 1 100%;
      }
      .ellipsis {
        max-width: 150px;
      }
      .engine-head,
      .hit-head {
        flex-wrap: wrap;
      }
    }
    @media (max-width: 480px) {
      .storage {
        padding: 12px 10px;
      }
      .ellipsis {
        max-width: 110px;
      }
      .metrics {
        grid-template-columns: repeat(auto-fit, minmax(min(100%, 140px), 1fr));
      }
    }
</style>
