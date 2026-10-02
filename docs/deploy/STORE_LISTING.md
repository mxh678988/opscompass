# 微软商店上架素材（Microsoft Store / Partner Center）

> 配套文档：[MSSTORE_GUIDE.md](./MSSTORE_GUIDE.md)（打包与提交流程）、[PUBLISH_CHECKLIST.md](./PUBLISH_CHECKLIST.md)（发布清单）
> 用途：Partner Center 提交时逐项复制粘贴，避免临场编写文案。
> 联系邮箱统一使用 **mxh6789@live.cn**；`mxh6789@gmail.com` 仅为 Cloudflare 账号标识，不得作为对外联系方式。

---

## 一、基础信息

| 字段 | 取值 |
| --- | --- |
| 应用名称（保留） | 运营智脑 |
| 英文名称 | OpsCompass |
| 版本号 | v0.10.1 |
| 分类 | 商务 / 工作效率（Business / Productivity） |
| 币种与定价 | 免费（Free） |
| 支持语言 | 简体中文（主）、英语（英区必备） |
| 官网 / 落地页 | Cloudflare Pages 部署地址（P1 完成后回填） |
| 隐私政策 URL | `https://<域名>/privacy.html`（P1 完成后回填） |
| 支持邮箱 | mxh6789@live.cn |
| 开发者 | BY LAOMENG 网络工作室 |

---

## 二、文案正文

### 1. 简短描述（Short description，≤ 100 字符）

**中文**：面向全域运营的一体化决策工具：多渠道数据接入、指标监控、AI 参谋与学习进化。

**English**：All-in-one operations decision hub: multi-channel data, KPI monitoring, AI advisor.

### 2. 详细描述（Description）

**中文版**

运营智脑（OpsCompass）是 BY LAOMENG 网络工作室面向全渠道运营场景打造的一体化决策工具。它把分散在各平台的数据汇聚到同一处，用统一的指标口径和 AI 参谋能力，帮助运营者快速看清现状、定位问题、做出决策。

核心能力：

- **多渠道数据接入**：支持电商、内容、广告等渠道数据的采集调度与导入，统一清洗入库。
- **全景罗盘与指标中心**：以罗盘视图与指标看板呈现核心经营指标，支持多维下钻与趋势对比。
- **运营参谋（AI）**：基于本地数据的问答与归因分析，直接给出经营异动的可能原因与处置建议。
- **营销渠道与商业化**：渠道效果对比、投放结构分析与商业化路径梳理。
- **模型中心与 AI 治理**：统一管理本地大模型接入，提供调用治理、安全日志与合规留痕。
- **学习进化**：沉淀运营经验，形成可复用的策略与知识库。
- **离线可用**：作为 PWA 应用安装到桌面后，可离线访问已缓存页面。

数据主权：应用默认在本地/自有服务器部署，业务数据不经第三方云端，适合对数据安全敏感的中小团队与个人运营者。

**English version**

OpsCompass is an all-in-one decision hub for full-channel operations, built by BY LAOMENG Studio. It consolidates data scattered across platforms into one place, and pairs a unified metric system with an AI advisor so operators can see the current state, locate problems, and act quickly.

Key capabilities:

- Multi-channel data ingestion with scheduled collection and unified cleansing.
- Compass view and metric center with drill-down and trend comparison.
- AI operations advisor: local-data Q&A and attribution analysis with concrete recommendations.
- Marketing channel and monetization analysis.
- Model center with AI governance, audit logs and compliance trails.
- Learning & evolution: turn operations experience into reusable playbooks.
- Offline ready: installable as a PWA with cached pages available offline.

Data sovereignty: designed for local or self-hosted deployment; business data stays off third-party clouds.

### 3. 功能要点（用于商店"功能"栏，各 ≤ 200 字符）

1. 多平台运营数据一站式汇聚，采集调度自动化。
2. 全景罗盘 + 指标中心，经营状况一屏掌握。
3. AI 运营参谋，异动归因与处置建议。
4. 营销渠道与商业化分析，投放结构一目了然。
5. 本地模型接入与 AI 治理，全程留痕可审计。
6. PWA 桌面安装，支持离线访问缓存页面。

### 4. 搜索关键词（Search terms，5 组以内）

`运营`、`数据分析`、`经营看板`、`AI 参谋`、`OpsCompass`

---

## 三、素材清单（提交前须齐备）

| 素材 | 规格要求 | 状态 |
| --- | --- | --- |
| 应用图标 | 300×300 PNG（商店主图），另需 44×44 / 50×50 / 150×150 | 待从 `frontend/public/icons/` 导出 |
| 桌面截图 | 1366×768 或 1920×1080，1–10 张，PNG | 待补（登录页、总览、罗盘、指标中心、AI 参谋） |
| 商店展示图 | 1920×1080 宣传图（可选） | 待补 |
| 隐私政策页 | 可公网访问的 HTTPS 链接 | 已生成 `privacy.html`，待 P1 托管后回填 URL |
| 应用包 | MSIX（见 MSSTORE_GUIDE 路线 A/B） | 待 P1 后由 PWABuilder 生成 |

截图拍摄建议顺序：登录页 → 运营总览 → 全景罗盘 → 指标中心 → 运营参谋问答 → 学习进化。

---

## 四、其他合规信息

- **AIGC 内容标识**：应用内含 AI 生成/辅助分析结果，界面已标注 AI 来源；商店描述中保留"AI 参谋"表述，不做绝对化效果承诺。
- **数据收集声明**：默认本地部署、不采集用户业务数据；如启用云端托管，需在隐私政策中补充说明。
- **未成年人**：本应用面向企业/个人运营者，不建议未成年人使用。
- **商标与署名**：应用名称与图标版权归 BY LAOMENG 网络工作室所有。
