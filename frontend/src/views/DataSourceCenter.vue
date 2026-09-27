<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createDataSource,
  deleteDataSource,
  fetchDataSources,
  updateDataSource,
  type DataSourceItem,
} from '@/api/datasources'

const rows = ref<DataSourceItem[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const editingCode = ref('')
const saving = ref(false)

const DS_TYPES = ['csv', 'api', 'mysql', 'postgresql', 'clickhouse', 'hive']

const form = reactive({
  code: '',
  name: '',
  ds_type: 'csv',
  host: '',
  port: '' as string | number,
  db_name: '',
  username: '',
  password: '',
  status: 'enabled',
})

function reset() {
  Object.assign(form, {
    code: '',
    name: '',
    ds_type: 'csv',
    host: '',
    port: '',
    db_name: '',
    username: '',
    password: '',
    status: 'enabled',
  })
  editingCode.value = ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchDataSources({ page: 1, page_size: 100 })
    rows.value = res.data.items ?? []
    total.value = res.data.total ?? 0
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? '加载失败'
  } finally {
    loading.value = false
  }
}

function edit(row: DataSourceItem) {
  editingCode.value = row.code
  Object.assign(form, {
    code: row.code,
    name: row.name,
    ds_type: row.ds_type,
    host: row.host ?? '',
    port: row.port ?? '',
    db_name: row.db_name ?? '',
    username: row.username ?? '',
    password: '',
    status: row.status,
  })
}

async function submit() {
  error.value = ''
  if (!form.code.trim() || !form.name.trim()) {
    error.value = '数据源编码与名称必填'
    return
  }
  saving.value = true
  const payload: any = {
    name: form.name,
    ds_type: form.ds_type,
    host: form.host || null,
    port: form.port === '' ? null : Number(form.port),
    db_name: form.db_name || null,
    username: form.username || null,
    status: form.status,
  }
  if (form.password) payload.password = form.password
  try {
    if (editingCode.value) {
      await updateDataSource(editingCode.value, payload)
    } else {
      await createDataSource({ ...payload, code: form.code.trim() })
    }
    reset()
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '保存失败（编码可能已存在）'
  } finally {
    saving.value = false
  }
}

async function toggle(row: DataSourceItem) {
  await updateDataSource(row.code, { status: row.status === 'enabled' ? 'disabled' : 'enabled' })
  await load()
}

async function remove(row: DataSourceItem) {
  if (!window.confirm(`确认删除数据源「${row.name}（${row.code}）」？`)) return
  await deleteDataSource(row.code)
  await load()
}

onMounted(load)
</script>

<template>
  <main class="data-source">
    <header class="head">
      <h1>数据源</h1>
      <p class="subtitle">管理指标数据的接入通道：文件导入（csv）、接口采集（api）与数据库直连</p>
    </header>

    <section class="panel">
      <h2>{{ editingCode ? `编辑数据源：${editingCode}` : '新建数据源' }}</h2>
      <form class="form" @submit.prevent="submit">
        <label>
          <span>编码 *</span>
          <input v-model="form.code" :disabled="!!editingCode" placeholder="如 tx_daily_report" />
        </label>
        <label>
          <span>名称 *</span>
          <input v-model="form.name" placeholder="如 腾讯日报导出" />
        </label>
        <label>
          <span>类型</span>
          <select v-model="form.ds_type">
            <option v-for="t in DS_TYPES" :key="t" :value="t">{{ t }}</option>
          </select>
        </label>
        <label>
          <span>主机</span>
          <input v-model="form.host" placeholder="可选" />
        </label>
        <label>
          <span>端口</span>
          <input v-model="form.port" type="number" min="1" max="65535" placeholder="可选" />
        </label>
        <label>
          <span>库名</span>
          <input v-model="form.db_name" placeholder="可选" />
        </label>
        <label>
          <span>用户名</span>
          <input v-model="form.username" placeholder="可选" />
        </label>
        <label>
          <span>密码</span>
          <input v-model="form.password" type="password" placeholder="仅写入，不回显" />
        </label>
        <label>
          <span>状态</span>
          <select v-model="form.status">
            <option value="enabled">启用</option>
            <option value="disabled">停用</option>
          </select>
        </label>
        <button class="primary" type="submit" :disabled="saving">
          {{ saving ? '保存中…' : editingCode ? '保存修改' : '创建数据源' }}
        </button>
        <button v-if="editingCode" type="button" @click="reset">取消编辑</button>
      </form>
    </section>

    <section class="panel">
      <h2>数据源列表（{{ total }}）</h2>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>编码</th>
            <th>名称</th>
            <th>类型</th>
            <th>地址</th>
            <th>状态</th>
            <th>最近同步</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td class="mono">{{ row.code }}</td>
            <td>{{ row.name }}</td>
            <td class="mono">{{ row.ds_type }}</td>
            <td class="mono">
              {{ row.host ? `${row.host}${row.port ? ':' + row.port : ''}` : '-' }}
            </td>
            <td>
              <span class="tag" :class="row.status">{{ row.status === 'enabled' ? '启用' : '停用' }}</span>
            </td>
            <td>{{ row.last_sync_at ?? '-' }}</td>
            <td class="ops">
              <button @click="edit(row)">编辑</button>
              <button @click="toggle(row)">{{ row.status === 'enabled' ? '停用' : '启用' }}</button>
              <button class="danger" @click="remove(row)">删除</button>
            </td>
          </tr>
          <tr v-if="!rows.length && !loading">
            <td colspan="7" class="empty">暂无数据源，请在上方创建</td>
          </tr>
        </tbody>
      </table>
      </div>
      <p v-if="loading" class="hint">加载中…</p>
    </section>
  </main>
</template>

<style scoped>
.data-source { padding: 32px; max-width: 1400px; margin: 0 auto; }
.subtitle { color: var(--color-text-secondary); margin-bottom: 24px; font-size: 14px; }
.panel { border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 20px; margin-bottom: 20px; background: var(--color-bg); }
.panel h2 { font-size: 15px; font-weight: 600; color: var(--color-text); margin: 0 0 14px; }
.form { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px 16px; align-items: end; }
.form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--color-text-secondary); }
select, input { padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; width: 100%; box-sizing: border-box; }
select:disabled, input:disabled { background: var(--color-border-light); color: var(--color-text-muted); }
button { padding: 8px 14px; border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-bg); cursor: pointer; font-size: 13px; }
button.primary { background: var(--color-primary); border-color: var(--color-primary); color: var(--color-bg); }
button.primary:disabled { opacity: 0.6; cursor: not-allowed; }
button.danger { color: var(--color-error); border-color: var(--color-error-border); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--color-border-light); white-space: nowrap; }
th { color: var(--color-text-secondary); font-weight: 500; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.ops button { margin-right: 6px; }
.tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; background: var(--color-bg-subtle); color: var(--color-text-secondary); }
.tag.enabled { background: var(--color-success-light); color: var(--color-success); }
.tag.disabled { background: var(--color-bg-subtle); color: var(--color-text-muted); }
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
      .data-source {
        padding: 20px 16px;
      }
    }
    @media (max-width: 768px) {
      .data-source {
        padding: 16px 12px;
      }
      .panel {
        padding: 16px;
      }
      .form {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 480px) {
      .data-source {
        padding: 12px 10px;
      }
    }
</style>
