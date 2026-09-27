<template>
  <div class="com-page">
    <header class="page-head">
      <div>
        <h2>商业化中心</h2>
        <p class="sub">套餐定价 · 授权证书（自有数字签名，可离线复算）· 订单 · 用量配额 · 授权校验</p>
      </div>
      <div class="head-ops">
        <button class="btn ghost" type="button" :disabled="loading" @click="loadAll">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="banner bad">{{ error }}</div>
    <div v-if="notice" class="banner ok">{{ notice }}</div>

    <section class="ent" v-if="ent">
      <div class="ent-main">
        <span class="tag" :class="ent.licensed ? 'ok' : 'warn'">
          {{ ent.licensed ? '已授权' : '社区版限额' }}
        </span>
        <strong>{{ ent.plan ? ent.plan.name : '未绑定套餐' }}</strong>
        <span v-if="ent.license" class="mono">{{ ent.license.license_key }}</span>
        <span v-if="ent.license && ent.license.expires_at">
          到期 {{ fmtDay(ent.license.expires_at) }}（剩 {{ ent.license.days_left }} 天）
        </span>
        <span v-else-if="ent.license">永久授权</span>
      </div>
      <div class="ent-hint">{{ ent.hint }}</div>
      <div class="ent-limits">
        <div class="lim" v-for="l in limitRows" :key="l.key">
          <span class="k">{{ l.label }}</span>
          <strong>{{ l.value }}</strong>
        </div>
      </div>
    </section>

    <nav class="tabs">
      <button
        v-for="t in TABS"
        :key="t.key"
        type="button"
        class="tab"
        :class="{ active: tab === t.key }"
        @click="switchTab(t.key)"
      >
        {{ t.label }}
      </button>
    </nav>

    <!-- ============================== 总览 ============================== -->
    <template v-if="tab === 'overview'">
      <section class="stats" v-if="ov">
        <div class="stat"><span class="k">套餐</span><strong>{{ ov.plans.total }}</strong></div>
        <div class="stat"><span class="k">在售</span><strong>{{ ov.plans.on_sale }}</strong></div>
        <div class="stat"><span class="k">授权总数</span><strong>{{ ov.licenses.total }}</strong></div>
        <div class="stat"><span class="k">生效授权</span><strong>{{ ov.licenses.active }}</strong></div>
        <div class="stat"><span class="k">待激活</span><strong>{{ ov.licenses.pending }}</strong></div>
        <div class="stat"><span class="k">即将到期</span><strong>{{ ov.licenses.expiring_soon }}</strong></div>
        <div class="stat"><span class="k">已过期</span><strong>{{ ov.licenses.expired }}</strong></div>
        <div class="stat"><span class="k">已吊销</span><strong>{{ ov.licenses.revoked }}</strong></div>
        <div class="stat"><span class="k">订单</span><strong>{{ ov.orders.total }}</strong></div>
        <div class="stat"><span class="k">已支付</span><strong>{{ ov.orders.paid }}</strong></div>
        <div class="stat"><span class="k">累计收入</span><strong>¥{{ money(ov.orders.revenue_total) }}</strong></div>
        <div class="stat"><span class="k">本月收入</span><strong>¥{{ money(ov.orders.revenue_month) }}</strong></div>
      </section>

      <section class="panel">
        <div class="panel-head"><h3>授权模式</h3></div>
        <div class="modes">
          <div class="mode" v-for="m in ov?.modes || []" :key="m.key">
            <div class="mode-name">{{ m.name }}</div>
            <div class="mode-desc">{{ m.desc }}</div>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3>上架前置门槛清单</h3>
          <span class="hint">人工确认项，系统不做自动判定</span>
        </div>
        <ul class="checklist">
          <li v-for="c in ov?.launch_checklist || []" :key="c.key">
            <span class="ck-dot"></span>
            <div>
              <div class="ck-label">{{ c.label }}</div>
              <div class="ck-hint">{{ c.hint }}</div>
            </div>
          </li>
        </ul>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3>近期订单</h3>
          <span class="hint">账期 {{ ov?.usage.period || '-' }} · 用量告警 {{ ov?.usage.warning || 0 }} / 超额 {{ ov?.usage.exceeded || 0 }}</span>
        </div>
        <table class="tbl">
          <thead>
            <tr><th>订单号</th><th>套餐</th><th>金额</th><th>状态</th><th>下单时间</th></tr>
          </thead>
          <tbody>
            <tr v-for="o in ov?.orders.recent || []" :key="o.id">
              <td class="mono">{{ o.order_no }}</td>
              <td>{{ o.plan_name }}</td>
              <td class="mono">¥{{ money(o.amount) }}</td>
              <td><span class="tag" :class="orderTag(o.status)">{{ ORDER_STATUS[o.status] || o.status }}</span></td>
              <td class="mono">{{ fmtDay(o.created_at) }}</td>
            </tr>
            <tr v-if="!(ov?.orders.recent || []).length"><td colspan="5" class="empty">暂无订单</td></tr>
          </tbody>
        </table>
      </section>
    </template>

    <!-- ============================== 套餐 ============================== -->
    <template v-else-if="tab === 'plan'">
      <section class="panel">
        <div class="panel-head">
          <h3>套餐定价</h3>
          <div class="head-ops">
            <input v-model="planFilter.keyword" class="ipt" placeholder="名称 / 编码" @keyup.enter="searchPlans" />
            <select v-model="planFilter.edition" class="ipt" @change="searchPlans">
              <option value="">全部形态</option>
              <option v-for="e in EDITIONS" :key="e.value" :value="e.value">{{ e.label }}</option>
            </select>
            <button class="btn ghost" type="button" @click="searchPlans">查询</button>
            <button class="btn ghost" type="button" @click="doSeed">重建内置套餐</button>
            <button class="btn primary" type="button" @click="openPlan(); showPlanDialog = true">新建套餐</button>
          </div>
        </div>
        <table class="tbl">
          <thead>
            <tr>
              <th>套餐</th><th>形态</th><th>计费</th><th>价格</th>
              <th>限额（账号/站点/指标/并发）</th>
              <th>上架</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in plans" :key="p.id">
              <td class="strong">
                {{ p.name }}
                <span class="mono" style="font-weight:400;margin-left:4px;">{{ p.code }}</span>
              </td>
              <td><span class="tag mono">{{ p.edition }}</span></td>
              <td class="mono">{{ p.billing_cycle }}</td>
              <td class="mono">¥{{ money(p.price) }}</td>
              <td class="mono">{{ p.seats_limit }} / {{ p.store_limit }} / {{ p.metric_limit }} / {{ p.user_limit }}</td>
              <td>
                <span class="tag" :class="p.status === 'on' ? 'ok' : ''">
                  {{ p.status === 'on' ? '上架' : '停售' }}
                </span>
              </td>
              <td class="ops">
                <button class="btn mini" type="button" @click="editPlan(p)">编辑</button>
                <button class="btn mini" type="button" @click="togglePlan(p)">{{ p.status === 'on' ? '停售' : '上架' }}</button>
                <button class="btn mini danger" type="button" @click="removePlan(p)">删除</button>
              </td>
            </tr>
            <tr v-if="!plans.length"><td colspan="7" class="empty">暂无套餐</td></tr>
          </tbody>
        </table>
        <div class="pager">
          <span>第 {{ planPage }} / {{ Math.max(1, Math.ceil(planTotal / planPageSize)) }} 页（共 {{ planTotal }} 个）</span>
          <div>
            <button class="btn mini ghost" :disabled="planPage <= 1" @click="turnPlan(-1)">上一页</button>
            <button class="btn mini ghost" :disabled="planPage >= Math.ceil(planTotal / planPageSize)" @click="turnPlan(1)">下一页</button>
          </div>
        </div>
      </section>
    </template>

    <!-- ============================== 授权 ============================== -->
    <template v-else-if="tab === 'license'">
      <section class="panel">
        <div class="panel-head">
          <h3>授权证书</h3>
          <div class="head-ops">
            <input v-model="licenseFilter.keyword" class="ipt" placeholder="授权码 / 授权对象 / 机器码" @keyup.enter="searchLicenses" />
            <select v-model="licenseFilter.status" class="ipt" @change="searchLicenses">
              <option value="">全部状态</option>
              <option v-for="s in LIC_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
            <select v-model="licenseFilter.licenseType" class="ipt" @change="searchLicenses">
              <option value="">全部形态</option>
              <option v-for="l in LIC_TYPES" :key="l.value" :value="l.value">{{ l.label }}</option>
            </select>
            <button class="btn ghost" type="button" @click="searchLicenses">查询</button>
            <button class="btn primary" type="button" @click="openIssue()">签发授权</button>
          </div>
        </div>
        <table class="tbl">
          <thead>
            <tr>
              <th>授权码</th><th>套餐</th><th>形态</th><th>账号数</th><th>状态</th>
              <th>到期</th><th>到期剩余</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="lic in licenses" :key="lic.id">
              <td class="mono" style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" :title="lic.license_key">
                {{ lic.license_key }}
              </td>
              <td>{{ lic.plan_name }}</td>
              <td><span class="tag mono">{{ lic.license_type }}</span></td>
              <td class="mono">{{ lic.seats }}</td>
              <td><span class="tag" :class="licStatusTag(lic)">{{ licStatusLabel(lic) }}</span></td>
              <td class="mono">{{ fmtDay(lic.expires_at) }}</td>
              <td class="mono" :class="lic.expiring_soon ? 'warn-text' : ''">{{ lic.days_left != null ? lic.days_left + ' 天' : '永久' }}</td>
              <td class="ops">
                <button class="btn mini" type="button" @click="doVerify(lic)">校验</button>
                <button class="btn mini" type="button" @click="doRenew(lic)">续期</button>
                <button class="btn mini" type="button" @click="doActivate(lic)">激活</button>
                <button class="btn mini danger" type="button" @click="doRevoke(lic)">吊销</button>
              </td>
            </tr>
            <tr v-if="!licenses.length"><td colspan="8" class="empty">暂无授权</td></tr>
          </tbody>
        </table>
        <div class="pager">
          <span>第 {{ licensePage }} / {{ Math.max(1, Math.ceil(licenseTotal / licensePageSize)) }} 页（共 {{ licenseTotal }} 个）</span>
          <div>
            <button class="btn mini ghost" :disabled="licensePage <= 1" @click="turnLicense(-1)">上一页</button>
            <button class="btn mini ghost" :disabled="licensePage >= Math.ceil(licenseTotal / licensePageSize)" @click="turnLicense(1)">下一页</button>
          </div>
        </div>
      </section>
    </template>

    <!-- ============================== 订单 ============================== -->
    <template v-else-if="tab === 'order'">
      <section class="panel">
        <div class="panel-head">
          <h3>订单管理</h3>
          <div class="head-ops">
            <input v-model="orderFilter.keyword" class="ipt" placeholder="订单号 / 购买方" @keyup.enter="searchOrders" />
            <select v-model="orderFilter.status" class="ipt" @change="searchOrders">
              <option value="">全部状态</option>
              <option v-for="s in ORDER_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
            <button class="btn ghost" type="button" @click="searchOrders">查询</button>
            <button class="btn primary" type="button" @click="openOrder()">创建订单</button>
          </div>
        </div>
        <table class="tbl">
          <thead>
            <tr>
              <th>订单号</th><th>套餐</th><th>金额</th><th>渠道</th><th>购买方</th><th>状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in orders" :key="o.id">
              <td class="mono">{{ o.order_no }}</td>
              <td>{{ o.plan_name }}</td>
              <td class="mono">¥{{ money(o.amount) }}</td>
              <td class="mono">{{ o.pay_channel }}</td>
              <td>{{ o.buyer || '-' }}</td>
              <td><span class="tag" :class="orderTag(o.status)">{{ ORDER_STATUS[o.status] || o.status }}</span></td>
              <td class="ops">
                <button v-if="o.status === 'pending'" class="btn mini primary" type="button" @click="doPay(o)">支付</button>
                <button v-if="o.status === 'pending'" class="btn mini" type="button" @click="doCancel(o)">取消</button>
                <span v-else class="hint">-</span>
              </td>
            </tr>
            <tr v-if="!orders.length"><td colspan="7" class="empty">暂无订单</td></tr>
          </tbody>
        </table>
        <div class="pager">
          <span>第 {{ orderPage }} / {{ Math.max(1, Math.ceil(orderTotal / orderPageSize)) }} 页（共 {{ orderTotal }} 个）</span>
          <div>
            <button class="btn mini ghost" :disabled="orderPage <= 1" @click="turnOrder(-1)">上一页</button>
            <button class="btn mini ghost" :disabled="orderPage >= Math.ceil(orderTotal / orderPageSize)" @click="turnOrder(1)">下一页</button>
          </div>
        </div>
      </section>
    </template>

    <!-- ============================== 用量 ============================== -->
    <template v-else-if="tab === 'usage'">
      <section class="panel">
        <div class="panel-head">
          <h3>用量配额</h3>
          <div class="head-ops">
            <input v-model="usageForm.metricKey" class="ipt" placeholder="指标标识（如 seats）" />
            <input v-model="usageForm.period" class="ipt" placeholder="账期 YYYY-MM（留空自动）" />
            <input v-model.number="usageForm.quota" class="ipt" placeholder="配额（0=不限）" style="width:120px" />
            <select v-model="usageForm.unit" class="ipt" style="width:90px">
              <option>count</option>
              <option>GB</option>
              <option>hour</option>
            </select>
            <button class="btn ghost" type="button" @click="searchUsage">查询</button>
            <button class="btn primary" type="button" @click="doUsage()">登记用量</button>
          </div>
        </div>
        <table class="tbl usage-tbl">
          <thead>
            <tr><th>指标</th><th>账期</th><th>已用</th><th>配额</th><th>占比</th><th>状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="u in usages" :key="u.id">
              <td class="mono">{{ u.metric_key }}</td>
              <td class="mono">{{ u.period }}</td>
              <td class="mono">{{ u.used }}</td>
              <td class="mono">{{ u.quota || '不限' }}</td>
              <td class="mono" :class="usageRatioClass(u)">{{ u.ratio != null ? (u.ratio * 100).toFixed(1) + '%' : '-' }}</td>
              <td><span class="tag" :class="u.status === 'exceeded' ? 'bad' : u.status === 'warning' ? 'warn' : ''">{{ USAGE_STATUS[u.status] || u.status }}</span></td>
              <td class="ops">
                <button class="btn mini" type="button" @click="editUsageQuota(u)">编辑配额</button>
              </td>
            </tr>
            <tr v-if="!usages.length"><td colspan="7" class="empty">暂无用量记录</td></tr>
          </tbody>
        </table>
        <div class="pager">
          <span>第 {{ usagePage }} / {{ Math.max(1, Math.ceil(usageTotal / usagePageSize)) }} 页（共 {{ usageTotal }} 个）</span>
          <div>
            <button class="btn mini ghost" :disabled="usagePage <= 1" @click="turnUsage(-1)">上一页</button>
            <button class="btn mini ghost" :disabled="usagePage >= Math.ceil(usageTotal / usagePageSize)" @click="turnUsage(1)">下一页</button>
          </div>
        </div>
      </section>
    </template>

    <!-- ============================== 授权校验 ============================== -->
    <template v-else-if="tab === 'verify'">
      <section class="panel">
        <div class="panel-head"><h3>授权校验（签名 / 状态 / 有效期 / 机器码四重校验，可离线复算）</h3></div>
        <form @submit.prevent="doVerifyDirect" class="verify-form">
          <div class="form-row">
            <div class="form-group"><label>授权码</label><input v-model="verifyForm.licenseKey" class="ipt" required /></div>
            <div class="form-group"><label>机器码（可选）</label><input v-model="verifyForm.machineCode" class="ipt" /></div>
            <div class="form-group"><button class="btn primary" type="submit">校验</button></div>
          </div>
        </form>
        <div v-if="verifyResult" class="verify-result" :class="verifyResult.valid ? 'ok' : 'bad'">
          <strong>{{ verifyResult.valid ? '校验通过' : '校验失败' }}</strong>
          <span>{{ verifyResult.reason }}</span>
          <div v-if="verifyResult.plan" class="mono">
            套餐：{{ verifyResult.plan.name }}（{{ verifyResult.plan.code }}）
          </div>
          <div v-if="verifyResult.license && verifyResult.license.license_key" class="mono">
            授权码：{{ verifyResult.license.license_key }}
          </div>
          <div v-if="verifyResult.license && verifyResult.license.expires_at" class="mono">
            到期：{{ fmtDay(verifyResult.license.expires_at) }}（剩 {{ verifyResult.license.days_left }} 天）
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head"><h3>授权事件留痕</h3></div>
        <table class="tbl">
          <thead><tr><th>操作</th><th>授权码</th><th>详情</th><th>操作人</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="e in events" :key="e.id">
              <td><span class="tag mono">{{ e.action }}</span></td>
              <td class="mono">{{ e.license_key }}</td>
              <td>{{ e.detail }}</td>
              <td class="mono">{{ e.operator }}</td>
              <td class="mono">{{ fmtDay(e.created_at) }}</td>
            </tr>
            <tr v-if="!events.length"><td colspan="5" class="empty">暂无事件</td></tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>

  <!-- 套餐弹窗 -->
  <div v-if="showPlanDialog" class="modal-overlay" @click.self="showPlanDialog = false">
    <div class="modal">
      <h3>{{ planForm.id ? '编辑套餐' : '新建套餐' }}</h3>
      <form @submit.prevent="submitPlan" class="modal-form">
        <div class="form-row">
          <div class="form-group"><label>套餐名称</label><input v-model="planForm.name" required /></div>
          <div class="form-group"><label>套餐编码</label><input v-model="planForm.code" required /></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>形态</label>
            <select v-model="planForm.edition">
              <option v-for="e in EDITIONS" :key="e.value" :value="e.value">{{ e.label }}</option>
            </select>
          </div>
          <div class="form-group"><label>计费</label>
            <select v-model="planForm.billing_cycle">
              <option value="one_time">一次性</option>
              <option value="subscription">订阅</option>
            </select>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>价格 (¥)</label><input v-model.number="planForm.price" type="number" min="0" /></div>
          <div class="form-group"><label>上架</label><input v-model="planForm.is_public" type="checkbox" /></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>账号数</label><input v-model.number="planForm.seats_limit" type="number" min="0" /></div>
          <div class="form-group"><label>站点数</label><input v-model.number="planForm.store_limit" type="number" min="0" /></div>
          <div class="form-group"><label>指标数</label><input v-model.number="planForm.metric_limit" type="number" min="0" /></div>
        </div>
        <div class="form-group"><label>备注</label><textarea v-model="planForm.remark" rows="2"></textarea></div>
        <div class="form-actions">
          <button type="submit" class="btn primary">保存</button>
          <button type="button" class="btn" @click="showPlanDialog = false">取消</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
// 商业化中心：套餐定价 / 授权证书 / 订单 / 用量配额 / 授权校验
import { computed, onMounted, reactive, ref } from 'vue'

import {
  activateLicense,
  cancelOrder,
  createOrder,
  createPlan,
  deletePlan,
  fetchEntitlement,
  fetchEvents,
  fetchLicenses,
  fetchOverview,
  fetchOrders,
  fetchPlans,
  fetchUsage,
  issueLicense,
  payOrder,
  renewLicense,
  revokeLicense,
  seedPlans,
  upsertUsage,
  updatePlan,
  verifyLicense,
  type ComEntitlement,
  type ComEvent,
  type ComLicense,
  type ComOrder,
  type ComPlan,
  type ComUsage,
  type ComVerifyResult,
} from '@/api/commercial'

const TABS = [
  { key: 'overview', label: '总览' },
  { key: 'plan', label: '套餐' },
  { key: 'license', label: '授权' },
  { key: 'order', label: '订单' },
  { key: 'usage', label: '用量' },
  { key: 'verify', label: '授权校验' },
]

const EDITIONS = [
  { value: 'private', label: '本地私有化' },
  { value: 'saas', label: 'SaaS 订阅' },
  { value: 'market', label: '应用市场' },
  { value: 'trial', label: '试用' },
]

const LIC_STATUSES = [
  { value: 'pending', label: '待激活' },
  { value: 'active', label: '生效' },
  { value: 'expired', label: '已过期' },
  { value: 'revoked', label: '已吊销' },
]

const LIC_TYPES = [
  { value: 'private', label: '私有化' },
  { value: 'saas', label: 'SaaS' },
  { value: 'market', label: '应用市场' },
  { value: 'trial', label: '试用' },
]

const ORDER_STATUSES = [
  { value: 'pending', label: '待支付' },
  { value: 'paid', label: '已支付' },
  { value: 'cancelled', label: '已取消' },
  { value: 'refunded', label: '已退款' },
]

const USAGE_STATUS: Record<string, string> = {
  normal: '正常',
  warning: '告警',
  exceeded: '超额',
}

const ORDER_STATUS: Record<string, string> = {
  pending: '待支付',
  paid: '已支付',
  cancelled: '已取消',
  refunded: '已退款',
}

const tab = ref<'overview' | 'plan' | 'license' | 'order' | 'usage' | 'verify' | 'events'>('overview')
const loading = ref(false)
const error = ref('')
const notice = ref('')
const showPlanDialog = ref(false)

const ov = ref<import('@/api/commercial').ComOverview | null>(null)
const ent = ref<ComEntitlement | null>(null)

const plans = ref<ComPlan[]>([])
const planTotal = ref(0)
const planPage = ref(1)
const planPageSize = 20
const planFilter = reactive({ keyword: '', edition: '' })

const licenses = ref<ComLicense[]>([])
const licenseTotal = ref(0)
const licensePage = ref(1)
const licensePageSize = 20
const licenseFilter = reactive({ keyword: '', status: '', licenseType: '' })

const orders = ref<ComOrder[]>([])
const orderTotal = ref(0)
const orderPage = ref(1)
const orderPageSize = 20
const orderFilter = reactive({ keyword: '', status: '' })

const usages = ref<ComUsage[]>([])
const usageTotal = ref(0)
const usagePage = ref(1)
const usagePageSize = 50
const usageForm = reactive({ metricKey: '', period: '', quota: 0, unit: 'count' })

const events = ref<ComEvent[]>([])

const verifyForm = reactive({ licenseKey: '', machineCode: '' })
const verifyResult = ref<ComVerifyResult | null>(null)

const planForm = reactive({
  id: 0 as number | '',
  name: '', code: '', edition: 'private' as string,
  billing_cycle: 'one_time' as string, price: 0,
  seats_limit: 5, store_limit: 1, metric_limit: 50, user_limit: 5,
  ai_quota: 0, is_public: true, sort: 0, remark: '',
})

const limitRows = computed(() => [
  { key: 'seats', label: '账号数', value: ent.value?.limits.seats || 0 },
  { key: 'stores', label: '站点数', value: ent.value?.limits.stores || 0 },
  { key: 'metrics', label: '指标数', value: ent.value?.limits.metrics || 0 },
  { key: 'users', label: '并发用户', value: ent.value?.limits.users || 0 },
  { key: 'ai', label: 'AI 配额', value: ent.value?.limits.ai_quota || 0 },
])

function fmtDay(d: string | null | undefined): string {
  if (!d) return '-'
  try {
    const dt = new Date(d)
    if (isNaN(dt.getTime())) return d.slice(0, 10)
    return dt.toLocaleDateString('zh-CN')
  } catch {
    return d.slice(0, 10)
  }
}

function money(v: number): string {
  return v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function licStatusLabel(lic: ComLicense): string {
  if (lic.status === 'revoked') return '已吊销'
  if (lic.status === 'expired') return '已过期'
  if (lic.status === 'pending') return '待激活'
  if (lic.expired) return '已过期'
  return '生效'
}

function licStatusTag(lic: ComLicense): string {
  if (lic.status === 'revoked') return 'bad'
  if (lic.status === 'expired' || lic.expired) return 'bad'
  if (lic.status === 'pending') return 'warn'
  return 'ok'
}

function orderTag(s: string): string {
  return s === 'paid' ? 'ok' : s === 'cancelled' || s === 'refunded' ? 'bad' : 'warn'
}

function usageRatioClass(u: ComUsage): string {
  if (u.status === 'exceeded') return 'bad-text'
  if (u.status === 'warning') return 'warn-text'
  return ''
}

function msg(e: any, fallback: string): string {
  return e?.response?.data?.detail ?? e?.message ?? fallback
}

function flash(text: string) {
  notice.value = text
  setTimeout(() => {
    if (notice.value === text) notice.value = ''
  }, 3200)
}

async function loadOverview() {
  const res = await fetchOverview()
  ov.value = res.data
}

async function loadEntitlement() {
  const res = await fetchEntitlement()
  ent.value = res.data
}

async function searchPlans() {
  const res = await fetchPlans({ keyword: planFilter.keyword || undefined, edition: planFilter.edition || undefined, page: planPage.value, size: planPageSize })
  plans.value = res.data.items
  planTotal.value = res.data.total
}

function openPlan() {
  planForm.id = 0
  planForm.name = ''
  planForm.code = ''
  planForm.edition = 'private'
  planForm.billing_cycle = 'one_time'
  planForm.price = 0
  planForm.seats_limit = 5
  planForm.store_limit = 1
  planForm.metric_limit = 50
  planForm.user_limit = 5
  planForm.ai_quota = 0
  planForm.is_public = true
  planForm.sort = 0
  planForm.remark = ''
}

function editPlan(p: ComPlan) {
  planForm.id = p.id
  planForm.name = p.name
  planForm.code = p.code
  planForm.edition = p.edition
  planForm.billing_cycle = p.billing_cycle
  planForm.price = p.price
  planForm.seats_limit = p.seats_limit
  planForm.store_limit = p.store_limit
  planForm.metric_limit = p.metric_limit
  planForm.user_limit = p.user_limit
  planForm.ai_quota = p.ai_quota
  planForm.is_public = p.is_public
  planForm.sort = p.sort
  planForm.remark = p.remark
}

async function submitPlan() {
  if (!planForm.code || !planForm.name) {
    error.value = '套餐编码和名称必填'
    return
  }
  try {
    if (planForm.id) {
      await updatePlan(planForm.id as number, planForm as Partial<ComPlan>)
      flash(`套餐「${planForm.name}」已更新`)
    } else {
      await createPlan(planForm as Partial<ComPlan>)
      flash(`套餐「${planForm.name}」已创建`)
    }
    openPlan()
    await searchPlans()
  } catch (e: any) {
    error.value = msg(e, '操作失败')
  }
}

async function togglePlan(p: ComPlan) {
  try {
    await updatePlan(p.id, { status: p.status === 'on' ? 'off' : 'on' })
    flash(`套餐「${p.name}」已${p.status === 'on' ? '停售' : '上架'}`)
    await searchPlans()
  } catch (e: any) {
    error.value = msg(e, '操作失败')
  }
}

async function removePlan(p: ComPlan) {
  try {
    await deletePlan(p.id)
    flash(`套餐「${p.name}」已删除`)
    await searchPlans()
  } catch (e: any) {
    error.value = msg(e, '操作失败')
  }
}

function doSeed() {
  seedPlans().then(res => {
    flash(`内置套餐已重置（新增 ${res.data.created} 档）`)
    return searchPlans()
  }).catch(e => { error.value = msg(e, '操作失败') })
}

function turnLicense(delta: number) {
  const next = licensePage.value + delta
  if (next < 1 || (next - 1) * licensePageSize >= licenseTotal.value) return
  licensePage.value = next
  searchLicenses()
}

function turnOrder(delta: number) {
  const next = orderPage.value + delta
  if (next < 1 || (next - 1) * orderPageSize >= orderTotal.value) return
  orderPage.value = next
  searchOrders()
}

function turnUsage(delta: number) {
  const next = usagePage.value + delta
  if (next < 1 || (next - 1) * usagePageSize >= usageTotal.value) return
  usagePage.value = next
  searchUsage()
}

function turnPlan(delta: number) {
  const next = planPage.value + delta
  if (next < 1 || (next - 1) * planPageSize >= planTotal.value) return
  planPage.value = next
  searchPlans()
}

async function searchLicenses() {
  const res = await fetchLicenses({
    keyword: licenseFilter.keyword || undefined,
    status: licenseFilter.status || undefined,
    license_type: licenseFilter.licenseType || undefined,
    page: licensePage.value,
    size: licensePageSize,
  })
  licenses.value = res.data.items
  licenseTotal.value = res.data.total
}

async function searchOrders() {
  const res = await fetchOrders({
    keyword: orderFilter.keyword || undefined,
    status: orderFilter.status || undefined,
    page: orderPage.value,
    size: orderPageSize,
  })
  orders.value = res.data.items
  orderTotal.value = res.data.total
}

async function searchUsage() {
  const res = await fetchUsage({
    period: usageForm.period || undefined,
    page: usagePage.value,
    size: usagePageSize,
  })
  usages.value = res.data.items
  usageTotal.value = res.data.total
}

function openIssue() {
  const issued_to = prompt('授权对象名称:')
  if (issued_to === null) return
  const seats = parseInt(prompt('授权账号数 (默认 1):', '1') ?? '', 10) || 1
  const days = parseInt(prompt('有效期天数 (默认 365, 0=永久):', '365') ?? '', 10) || 365
  issueLicense({ seats, issued_to: issued_to ?? '未指定', days }).then(res => {
    flash(`授权「${res.data.license_key}」已签发`)
    searchLicenses()
  }).catch(e => { error.value = msg(e, '签发失败') })
}

async function doVerify(lic: ComLicense) {
  try {
    const res = await verifyLicense({ license_key: lic.license_key })
    verifyResult.value = res.data
    if (res.data.valid) flash('授权校验通过')
  } catch (e: any) {
    error.value = msg(e, '校验失败')
  }
}

async function doRenew(lic: ComLicense) {
  const days = parseInt(prompt('续期天数 (默认 365):', '365') ?? '', 10) || 365
  try {
    await renewLicense(lic.id, days)
    flash(`授权已续期 ${days} 天`)
    searchLicenses()
  } catch (e: any) {
    error.value = msg(e, '续期失败')
  }
}

async function doActivate(lic: ComLicense) {
  const mc = prompt('机器码 (留空仅切换为生效态):', '')
  try {
    await activateLicense(lic.id, mc ?? '')
    flash('授权已激活')
    searchLicenses()
  } catch (e: any) {
    error.value = msg(e, '激活失败')
  }
}

async function doRevoke(lic: ComLicense) {
  const reason = prompt('吊销原因:', '用户申请')
  if (reason === null) return
  try {
    await revokeLicense(lic.id, reason)
    flash('授权已吊销')
    searchLicenses()
  } catch (e: any) {
    error.value = msg(e, '吊销失败')
  }
}

function openOrder() {
  const pid = parseInt(prompt('套餐 ID (留空取首个上架套餐):', '') ?? '', 10)
  const buyer = prompt('购买方:', '')
  const contact = prompt('联系人电话:', '')
  const payChannel = prompt('支付渠道 (wechat/alipay/offline):', 'offline')
  createOrder({ plan_id: pid || undefined, buyer: buyer ?? '', contact: contact ?? '', pay_channel: payChannel ?? 'offline' })
    .then(res => {
      flash(`订单「${res.data.order_no}」已创建`)
      searchOrders()
    })
    .catch(e => { error.value = msg(e, '创建失败') })
}

async function doPay(order: ComOrder) {
  const machineCode = prompt('机器码 (用于绑定授权):', '')
  const days = parseInt(prompt('授权有效期天数 (默认 365):', '365') ?? '', 10) || 365
  try {
    const res = await payOrder(order.id, { pay_channel: order.pay_channel, machine_code: machineCode ?? '', days })
    flash(`订单已支付，授权已签发 (${res.data.license_id})`)
    searchOrders()
  } catch (e: any) {
    error.value = msg(e, '支付失败')
  }
}

async function doCancel(order: ComOrder) {
  const reason = prompt('取消原因:', '')
  if (reason === null) return
  try {
    await cancelOrder(order.id, reason)
    flash('订单已取消')
    searchOrders()
  } catch (e: any) {
    error.value = msg(e, '取消失败')
  }
}

async function doUsage() {
  if (!usageForm.metricKey || !usageForm.period) {
    error.value = '指标标识和账期必填'
    return
  }
  try {
    await upsertUsage({
      metric_key: usageForm.metricKey,
      period: usageForm.period,
      quota: usageForm.quota,
      unit: usageForm.unit,
    })
    flash('用量已更新')
    searchUsage()
  } catch (e: any) {
    error.value = msg(e, '操作失败')
  }
}

async function editUsageQuota(u: ComUsage) {
  const newQuota = prompt('新配额 (0=不限):', String(u.quota || 0))
  if (newQuota === null) return
  const quota = parseInt(newQuota, 10)
  if (isNaN(quota) || quota < 0) { error.value = '配额必须为非负整数'; return }
  try {
    await upsertUsage({ metric_key: u.metric_key, period: u.period, quota })
    flash('配额已更新')
    searchUsage()
  } catch (e: any) {
    error.value = msg(e, '操作失败')
  }
}

async function doVerifyDirect() {
  if (!verifyForm.licenseKey) { error.value = '请输入授权码'; return }
  try {
    const res = await verifyLicense({ license_key: verifyForm.licenseKey, machine_code: verifyForm.machineCode ?? '' })
    verifyResult.value = res.data
    if (res.data.valid) flash('授权校验通过')
  } catch (e: any) {
    error.value = msg(e, '校验失败')
  }
}

function switchTab(key: string) {
  tab.value = key as typeof tab.value
  if (key === 'plan') searchPlans()
  else if (key === 'license') searchLicenses()
  else if (key === 'order') searchOrders()
  else if (key === 'usage') searchUsage()
  else if (key === 'verify') {
    fetchEvents(100).then(res => { events.value = res.data.items })
  }
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadOverview(), loadEntitlement()])
    switchTab(tab.value)
  } catch (e: any) {
    error.value = msg(e, '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadOverview()
  loadEntitlement()
  searchPlans()
})
</script>

<style scoped>
.commercial-center { max-width: 1200px; margin: 0 auto; padding: 24px 0; }

.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border-color); }
.page-header h2 { font-size: 1.6em; margin: 0; color: var(--text-primary); }

.banner { background: linear-gradient(135deg, var(--primary-light-bg), var(--secondary-light-bg)); padding: 20px 24px; border-radius: 12px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; }
.banner-text h3 { margin: 0 0 8px; color: var(--primary); }
.banner-text p { margin: 0; opacity: 0.8; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.stat-card { background: white; border-radius: 10px; padding: 18px 20px; border: 1px solid var(--border-color); }
.stat-card .stat-label { font-size: 0.85em; color: var(--text-secondary); margin-bottom: 4px; }
.stat-card .stat-value { font-size: 1.6em; font-weight: 700; color: var(--text-primary); }
.stat-card .stat-value.good { color: var(--success-color); }
.stat-card .stat-value.warn { color: var(--warning-color); }

.tabs { display: flex; gap: 4px; margin-bottom: 20px; background: var(--bg-secondary); border-radius: 10px; padding: 4px; flex-wrap: wrap; }
.tab-btn { padding: 8px 18px; border: none; background: none; border-radius: 8px; cursor: pointer; font-size: 0.9em; color: var(--text-secondary); transition: all 0.2s; }
.tab-btn:hover { background: white; color: var(--text-primary); }
.tab-btn.active { background: white; color: var(--primary); font-weight: 600; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }

.panel { background: white; border-radius: 12px; border: 1px solid var(--border-color); padding: 24px; margin-bottom: 20px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
.panel-head h3 { margin: 0; font-size: 1.2em; color: var(--text-primary); }

.head-ops { display: flex; gap: 8px; flex-wrap: wrap; }
.ipt { padding: 6px 12px; border: 1px solid var(--border-color); border-radius: 6px; font-size: 0.85em; background: white; }
.ipt:focus { outline: none; border-color: var(--primary); }

.btn { padding: 6px 16px; border: 1px solid var(--border-color); border-radius: 6px; background: white; color: var(--text-primary); cursor: pointer; font-size: 0.85em; transition: all 0.2s; }
.btn:hover { background: var(--bg-secondary); }
.btn.primary { background: var(--primary); color: white; border-color: var(--primary); }
.btn.primary:hover { opacity: 0.9; }
.btn.ghost { border-color: transparent; color: var(--text-secondary); }
.btn.ghost:hover { color: var(--text-primary); background: var(--bg-secondary); }
.btn.danger { background: #fef0f0; border-color: #fecaca; color: #dc2626; }
.btn.danger:hover { background: #fee2e2; }
.btn.mini { padding: 4px 10px; font-size: 0.8em; }

table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border-color); font-size: 0.9em; }
th { background: var(--bg-secondary); color: var(--text-secondary); font-weight: 600; }
tbody tr:hover { background: var(--bg-secondary); }
.tag { display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 0.8em; margin: 0 2px; }
.tag.ok { background: #dcfce7; color: #16a34a; }
.tag.warn { background: #fef9c3; color: #ca8a04; }
.tag.bad { background: #fef2f2; color: #dc2626; }
.tag.mono { font-family: 'JetBrains Mono', 'SF Mono', monospace; }
.mono { font-family: 'JetBrains Mono', 'SF Mono', monospace; }
.empty { text-align: center; color: var(--text-secondary); padding: 32px; }
.ops button { margin-right: 4px; }
.strong { font-weight: 600; }
.empty { text-align: center; color: var(--text-secondary); padding: 24px; }
.empty { text-align: center; color: var(--text-secondary); padding: 24px; }

.pager { display: flex; justify-content: space-between; align-items: center; padding-top: 16px; font-size: 0.85em; color: var(--text-secondary); }

.warn-text { color: var(--warning-color); }
.bad-text { color: #dc2626; }

.verify-form { margin-top: 12px; }
.form-row { display: flex; gap: 12px; flex-wrap: wrap; }
.form-group { flex: 1; min-width: 200px; }
.form-group label { display: block; margin-bottom: 4px; font-size: 0.85em; color: var(--text-secondary); }
.form-group .ipt { width: 100%; box-sizing: border-box; }

/* 用量表首列（指标标识）留足宽度，避免 seats / api_calls 被截断 */
.usage-tbl th:first-child,
.usage-tbl td:first-child { min-width: 150px; white-space: nowrap; }
.usage-tbl th:nth-child(2),
.usage-tbl td:nth-child(2) { min-width: 96px; white-space: nowrap; }

.verify-result { margin-top: 16px; padding: 16px; border-radius: 8px; border: 1px solid var(--border-color); }
.verify-result.ok { background: #f0fdf4; border-color: #bbf7d0; }
.verify-result.bad { background: #fef2f2; border-color: #fecaca; }
.verify-result strong { font-size: 1.1em; }

.toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); padding: 10px 24px; border-radius: 8px; background: white; box-shadow: 0 4px 20px rgba(0,0,0,0.12); z-index: 999; font-size: 0.9em; transition: opacity 0.3s; }
.toast.error { border-left: 4px solid #dc2626; }
.toast.success { border-left: 4px solid #16a34a; }
.toast.error { border-left: 4px solid #dc2626; }
.toast.success { border-left: 4px solid #16a34a; }
</style>
