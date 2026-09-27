<script setup lang="ts">
// 安全日志分级运维台：分级统计 / 条目筛选 / 高危告警 / 通道配置
import { computed, onMounted, reactive, ref } from 'vue'

import {
  fetchSecurityLogEntries,
  fetchSecurityLogLevels,
  type SecurityLogCatalog,
  type SecurityLogEntries,
} from '@/api/audit'

const LEVEL_TAG: Record<string, string> = {
  INFO: 'ok',
  WARNING: 'warn',
  CRITICAL: 'bad',
}

const catalog = ref<SecurityLogCatalog | null>(null)
const entries = ref<SecurityLogEntries | null>(null)
const loading = ref(false)
const error = ref('')

const form = reactive({
  level: '',
  event_type: '',
  days: 7,
  limit: 50,
})

const stats = computed(() => entries.value?.stats ?? null)
const config = computed(() => catalog.value?.config ?? null)
const fileMeta = computed(() => stats.value?.file ?? config.value?.file ?? null)

const byLevel = computed(() => {
  const raw = stats.value?.by_level ?? {}
  return (catalog.value?.levels ?? []).map((lv) => ({
    ...lv,
    count: Number(raw[lv.value] ?? 0),
  }))
})

const topEvents = computed(() =>
  Object.entries(stats.value?.by_event ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([value, count]) => ({
      value,
      count,
      label: (catalog.value?.events ?? []).find((e) => e.value === value)?.label ?? value,
    })),
)

function fmtSize(bytes?: number) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [cat, res] = await Promise.all([
      fetchSecurityLogLevels(),
      fetchSecurityLogEntries({
        level: form.level || undefined,
        event_type: form.event_type || undefined,
        days: Number(form.days) || 7,
        limit: Number(form.limit) || 50,
      }),
    ])
    catalog.value = cat.data
    entries.value = res.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <main class="security-log">
    <h1>安全日志</h1>
    <p class="subtitle">
      分级独立通道（INFO / WARNING / CRITICAL），与审计库双轨并行：审计库负责检索流水，分级通道负责告警与排障。
    </p>

    <p v-if="error" class="error">{{ error }}</p>

    <!-- 分级统计 -->
    <div class="metrics">
      <div class="metric">
        <span class="label">近 {{ stats?.days ?? form.days }} 天条目</span>
        <strong>{{ stats?.total ?? '-' }}</strong>
      </div>
      <div v-for="lv in byLevel" :key="lv.value" class="metric">
        <span class="label">
          <span class="tag" :class="LEVEL_TAG[lv.value] ?? 'muted'">{{ lv.label }}</span>
          {{ lv.value }}
        </span>
        <strong>{{ lv.count }}</strong>
      </div>
      <div class="metric">
        <span class="label">日志文件</span>
        <strong>{{ fmtSize(fileMeta?.size_bytes) }}</strong>
        <span class="mono small">{{ fileMeta?.path ?? '-' }}</span>
      </div>
    </div>

    <!-- 通道配置 -->
    <section class="panel">
      <h2>分级通道配置</h2>
      <div class="summary">
        <span class="tag" :class="config?.enabled ? 'ok' : 'muted'">
          {{ config?.enabled ? '已启用' : '已停用' }}
        </span>
        <span>最低记录级别 <strong>{{ config?.min_level ?? '-' }}</strong></span>
        <span>主日志告警级别 <strong>{{ config?.alert_level ?? '-' }}</strong></span>
        <span>WARNING 镜像主日志 <strong>{{ config?.mirror_to_main ? '开' : '关' }}</strong></span>
        <span v-if="fileMeta">
          单文件上限 <strong>{{ fmtSize(fileMeta.max_bytes) }}</strong> · 备份 <strong>{{ fileMeta.backup_count }}</strong> 份
        </span>
      </div>
      <ul class="levels">
        <li v-for="lv in catalog?.levels ?? []" :key="lv.value">
          <span class="tag" :class="LEVEL_TAG[lv.value] ?? 'muted'">{{ lv.value }}</span>
          <span class="desc">{{ lv.description }}</span>
        </li>
      </ul>
    </section>

    <!-- 条目筛选 -->
    <section class="panel">
      <h2>分级条目</h2>
      <div class="form">
        <label>
          <span>级别</span>
          <select v-model="form.level">
            <option value="">全部</option>
            <option v-for="lv in catalog?.levels ?? []" :key="lv.value" :value="lv.value">
              {{ lv.value }} · {{ lv.label }}
            </option>
          </select>
        </label>
        <label>
          <span>事件类型</span>
          <select v-model="form.event_type">
            <option value="">全部</option>
            <option v-for="ev in catalog?.events ?? []" :key="ev.value" :value="ev.value">
              {{ ev.label }}（{{ ev.default_level }}）
            </option>
          </select>
        </label>
        <label>
          <span>统计天数</span>
          <input v-model="form.days" type="number" min="1" max="365" />
        </label>
        <label>
          <span>条数上限</span>
          <input v-model="form.limit" type="number" min="1" max="200" />
        </label>
        <button class="primary" :disabled="loading" @click="load">
          {{ loading ? '查询中…' : '查询' }}
        </button>
      </div>

      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>级别</th>
            <th>事件</th>
            <th>用户</th>
            <th>IP</th>
            <th>方法</th>
            <th>路径</th>
            <th>状态码</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in entries?.items ?? []" :key="`${item.time}-${idx}`">
            <td class="mono">{{ item.time }}</td>
            <td><span class="tag" :class="LEVEL_TAG[item.level] ?? 'muted'">{{ item.level }}</span></td>
            <td>{{ item.event_label }}</td>
            <td>{{ item.username ?? '-' }}</td>
            <td class="mono">{{ item.ip ?? '-' }}</td>
            <td class="mono">{{ item.method ?? '-' }}</td>
            <td class="mono ellipsis">{{ item.path ?? '-' }}</td>
            <td class="mono">{{ item.status_code ?? '-' }}</td>
            <td class="detail ellipsis" :title="item.detail ?? ''">{{ item.detail ?? '-' }}</td>
          </tr>
          <tr v-if="!(entries?.items ?? []).length && !loading">
            <td colspan="9" class="empty">该筛选条件下暂无安全日志</td>
          </tr>
        </tbody>
      </table>
      </div>
      <p v-if="loading" class="hint">加载中…</p>
    </section>

    <!-- 事件分布与高危 -->
    <section class="panel">
      <h2>事件分布</h2>
      <ul v-if="topEvents.length" class="stats">
        <li v-for="ev in topEvents" :key="ev.value">
          <span>{{ ev.label }}</span>
          <em>{{ ev.count }}</em>
        </li>
      </ul>
      <p v-else class="empty">近 {{ stats?.days ?? form.days }} 天无事件记录</p>

      <h3 class="sub">最近高危事件（CRITICAL）</h3>
      <ul v-if="stats?.latest_critical?.length" class="criticals">
        <li v-for="(item, idx) in stats.latest_critical" :key="`${item.time}-${idx}`">
          <span class="mono">{{ item.time }}</span>
          <span class="tag bad">{{ item.event_label }}</span>
          <span class="mono">{{ item.username ?? '-' }} @ {{ item.ip ?? '-' }}</span>
          <span class="desc">{{ item.detail ?? '-' }}</span>
        </li>
      </ul>
      <p v-else class="empty">近 {{ stats?.days ?? form.days }} 天无高危事件</p>
    </section>
  </main>
</template>

<style scoped>
.security-log { padding: 32px; max-width: 1400px; margin: 0 auto; }
.subtitle { color: var(--color-text-secondary); margin-bottom: 24px; font-size: 14px; }
.panel { border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 20px; margin-bottom: 20px; background: var(--color-bg); }
.panel h2 { font-size: 15px; font-weight: 600; color: var(--color-text); margin: 0 0 14px; }
.sub { font-size: 14px; margin: 22px 0 10px; color: var(--color-text); }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 18px; }
.metric { border: 1px solid var(--color-border-light); border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; }
.metric .label { font-size: 12px; color: var(--color-text-secondary); display: flex; align-items: center; gap: 6px; }
.metric strong { font-size: 20px; }
.small { font-size: 11px; color: var(--color-text-muted); }
.form { display: flex; flex-wrap: wrap; gap: 12px 16px; align-items: end; margin-bottom: 12px; }
.form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--color-text-secondary); min-width: 170px; }
select, input { padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; width: 100%; box-sizing: border-box; }
button { padding: 8px 14px; border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-bg); cursor: pointer; font-size: 13px; }
button.primary { background: var(--color-primary); border-color: var(--color-primary); color: var(--color-bg); }
button:disabled { opacity: 0.6; cursor: not-allowed; }
table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 6px; }
th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--color-border-light); }
th { color: var(--color-text-secondary); font-weight: 500; white-space: nowrap; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.ellipsis { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.detail { max-width: 260px; }
.tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; background: var(--color-bg-subtle); color: var(--color-text-muted); }
.tag.ok { background: var(--color-success-light); color: var(--color-success); }
.tag.warn { background: var(--color-warning-light); color: var(--color-warning); }
.tag.bad { background: var(--color-error-light); color: var(--color-error); }
.tag.muted { background: var(--color-bg-subtle); color: var(--color-text-muted); }
.summary { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; font-size: 13px; color: var(--color-text-secondary); margin-bottom: 10px; }
.levels { list-style: none; margin: 0; padding: 0; font-size: 13px; }
.levels li { display: flex; align-items: flex-start; gap: 10px; padding: 5px 0; }
.levels .desc { color: var(--color-text-secondary); }
.stats { list-style: none; margin: 0; padding: 0; font-size: 13px; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 6px 18px; }
.stats li { display: flex; justify-content: space-between; gap: 8px; color: var(--color-text-secondary); border-bottom: 1px dashed var(--color-border-light); padding: 4px 0; }
.stats em { font-style: normal; color: var(--color-text); }
.criticals { list-style: none; margin: 0; padding: 0; font-size: 13px; }
.criticals li { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 6px 0; border-bottom: 1px solid var(--color-border-light); }
.criticals .desc { color: var(--color-text-secondary); }
.empty, .hint { color: var(--color-text-muted); font-size: 13px; }
.error { color: var(--color-error); margin: 8px 0; font-size: 13px; }

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
    @media (max-width: 1024px) {
      .security-log {
        padding: 20px 16px;
      }
    }
    @media (max-width: 768px) {
      .security-log {
        padding: 16px 12px;
      }
      .panel {
        padding: 16px;
      }
      .metrics {
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      }
      .form label {
        min-width: 0;
        flex: 1 1 100%;
      }
      .ellipsis {
        max-width: 150px;
      }
      .detail {
        max-width: 100%;
      }
      .levels li,
      .stats li,
      .criticals li {
        flex-wrap: wrap;
      }
    }
    @media (max-width: 480px) {
      .security-log {
        padding: 12px 10px;
      }
      .ellipsis {
        max-width: 110px;
      }
      .metrics {
        grid-template-columns: 1fr 1fr;
      }
    }
</style>
