# 运营智脑 OpsCompass · Microsoft Store（Partner Center）提审表单填写稿

> 生成时间：2026-10-03 | 适用版本：v0.10.1+ | 对应流程阶段：S1-P4（提交审核）
> 配套文档：[MSSTORE_GUIDE.md](./MSSTORE_GUIDE.md)（打包与流程）、[STORE_LISTING.md](./STORE_LISTING.md)（双语文案与素材）、[PUBLISH_CHECKLIST.md](./PUBLISH_CHECKLIST.md)（发布清单）
> 用途：Partner Center「新提交」页面逐字段复制粘贴，避免临场编写。
> 标记约定：**✅ 可直接照抄** / **⏳ 待 P2 回填**（P2 = 老板本人实名注册 Partner Center 并预留产品名称后，回填产品标识与正式包）

---

## 〇、填写总览（字段状态速查）

| # | Partner Center 区块 | 字段 | 状态 | 取值 / 指向 |
|---|---|---|---|---|
| 1 | Packages | 安装包 | ⏳ 待 P2 回填 | 正式 `.msixbundle` 须待真实包标识重打 |
| 2 | Packages | 三项包标识 | ⏳ 待 P2 回填 | 见 §七 |
| 3 | Store listing | 产品名称 | ✅ | 运营智脑（OpsCompass） |
| 4 | Store listing | 描述（Description） | ✅ | 见 §3.1（中/英） |
| 5 | Store listing | 功能（Product features） | ✅ | 见 §3.2（6 条） |
| 6 | Store listing | 搜索词（Search terms） | ✅ | 见 §3.3（7 个） |
| 7 | Store listing | 版权与商标 | ✅ | 见 §3.4 |
| 8 | Store listing | 系统要求 | ✅ | 见 §3.5（含 Docker 依赖声明） |
| 9 | Store listing | 商店图标（300×300） | ✅ | `docs/deploy/store-assets/icon-512-300x300.png` |
| 10 | Store listing | 截图（1–10 张） | ✅ 2 张（可补拍） | 见 §四 |
| 11 | Store listing | 隐私政策 URL | ✅ | `https://opscompass.pages.dev/privacy` |
| 12 | Store listing | 支持联系方式 | ✅ | 邮箱 `mxh6789@live.cn`；支持 URL 见 §六 |
| 13 | Pricing and availability | 定价 / 市场 / 语言 | ✅ | 免费 / 全球 / zh-CN + en-US |
| 14 | Properties | 类别（Category） | ✅ | 商务 · 工作效率（Business · Productivity） |
| 15 | Age rating | IARC 问卷与分级 | ⏳ 待填问卷 | 建议答案见 §五.4；`iarc_rating_id` 待回填 |

---

## 一、产品名称（Product name）

| 字段 | 可直接照抄的值 |
|---|---|
| 预留产品名称（提交前先在「产品标识」页确认） | `运营智脑` |
| 英文名称（英文列表页展示用） | `OpsCompass` |
| 建议商店展示名（若产品名可拼接） | `运营智脑 OpsCompass` |

> 说明：产品名称一旦提交审核即被锁定，改动需重新提审。请在 P2 阶段**先预留、后打包**，保证包内 `Identity` 与预留名称一致。

---

## 二、类别、定价与可用性

| 字段 | 可直接照抄的值 |
|---|---|
| 类别（Category） | 商务（Business） |
| 子类别（Subcategory） | 工作效率（Productivity） |
| 定价（Price） | 免费（Free） |
| 试用 / 内购 | 无 |
| 市场（Markets） | 全部可用市场（默认全球，近 200 个市场）；如有区域限制再行排除 |
| 支持语言（Languages） | 简体中文（zh-CN，主）、英语（en-US，英区必备） |
| 发布日期（Discoverability / Schedule） | 审核通过后尽快（「尽快发布」选项） |
| 可见性 | 公开（Public） |

---

## 三、商店列表页（Store listing）

### 3.1 描述（Description）

> 字段口径：Partner Center 的 Description 为**一整段富文本**；下列中文版可直接整体粘贴，英文区（en-US）粘贴 English version。

**中文版（可直接照抄）**

```
运营智脑（OpsCompass）是 BY LAOMENG 网络工作室面向全渠道运营场景打造的一体化决策工具。它把分散在各平台的数据汇聚到同一处，用统一的指标口径和 AI 参谋能力，帮助运营者快速看清现状、定位问题、做出决策。

核心能力：
· 多渠道数据接入：支持电商、内容、广告等渠道数据的采集调度与导入，统一清洗入库。
· 全景罗盘与指标中心：以罗盘视图与指标看板呈现核心经营指标，支持多维下钻与趋势对比。
· 运营参谋（AI）：基于本地数据的问答与归因分析，直接给出经营异动的可能原因与处置建议。
· 营销渠道与商业化：渠道效果对比、投放结构分析与商业化路径梳理。
· 模型中心与 AI 治理：统一管理本地大模型接入，提供调用治理、安全日志与合规留痕。
· 学习进化：沉淀运营经验，形成可复用的策略与知识库。
· 离线可用：作为 PWA 应用安装到桌面后，可离线访问已缓存页面。

数据主权：应用默认在本地/自有服务器部署，业务数据不经第三方云端，适合对数据安全敏感的中小团队与个人运营者。

运行说明：本应用为 PWA 应用，桌面端通过 Microsoft Store 安装后即可打开；如需完整私有化部署（含后端服务与本地数据库），需另行准备 Docker Desktop 环境，详见应用内首次启动引导。
```

**English version（可直接照抄，en-US 市场）**

```
OpsCompass is an all-in-one decision hub for full-channel operations, built by BY LAOMENG Studio. It consolidates data scattered across platforms into one place, and pairs a unified metric system with an AI advisor so operators can see the current state, locate problems, and act quickly.

Key capabilities:
· Multi-channel data ingestion with scheduled collection and unified cleansing.
· Compass view and metric center with drill-down and trend comparison.
· AI operations advisor: local-data Q&A and attribution analysis with concrete recommendations.
· Marketing channel and monetization analysis.
· Model center with AI governance, audit logs and compliance trails.
· Learning & evolution: turn operations experience into reusable playbooks.
· Offline ready: installable as a PWA with cached pages available offline.

Data sovereignty: designed for local or self-hosted deployment; business data stays off third-party clouds.

Note: this app is a PWA. The Store package launches the app directly; a full self-hosted deployment (backend services and local database) requires Docker Desktop, as guided in the in-app first-run walkthrough.
```

### 3.2 功能（Product features，各 ≤ 200 字符，可直接逐条粘贴）

| # | 功能文案（中文） | Feature text (English) |
|---|---|---|
| 1 | 多平台运营数据一站式汇聚，采集调度自动化。 | One-stop aggregation of multi-platform operations data with automated collection. |
| 2 | 全景罗盘 + 指标中心，经营状况一屏掌握。 | Compass view plus metric center: business status at a glance. |
| 3 | AI 运营参谋，异动归因与处置建议。 | AI operations advisor for anomaly attribution and action suggestions. |
| 4 | 营销渠道与商业化分析，投放结构一目了然。 | Marketing channel and monetization analysis with clear campaign structure. |
| 5 | 本地模型接入与 AI 治理，全程留痕可审计。 | Local model integration with AI governance and auditable trails. |
| 6 | PWA 桌面安装，支持离线访问缓存页面。 | Installable PWA for desktop with offline access to cached pages. |

### 3.3 搜索词（Search terms，最多 7 个，每个 ≤ 30 字符）

`运营` · `数据分析` · `经营看板` · `AI 参谋` · `OpsCompass` · `运营决策` · `指标监控`

### 3.4 版权与商标（Copyright and trademark）

| 字段 | 可直接照抄的值 |
|---|---|
| 版权（Copyright） | `© 2026 BY LAOMENG 网络工作室` |
| 商标信息 | `运营智脑、OpsCompass 为 BY LAOMENG 网络工作室所有` |
| 开发者（Publisher display name） | `BY LAOMENG 网络工作室`（正式值以 Partner Center 产品标识为准，见 §七） |

### 3.5 系统要求（System requirements）与 Docker 依赖声明

**System requirements 字段（可直接照抄）**

```
操作系统：Windows 10（1809 / Build 17763）或更高版本，或 Windows 11，64 位
处理器：x64（ARM64 视兼容包情况另议）
磁盘空间：≥ 5 GB（含 Docker 镜像，私有化部署场景）
运行时依赖：完整私有化部署需 Docker Desktop 4.0+ 与 PowerShell 5.1+
显示器：分辨率 1366×768 或更高
网络：首次安装与私有化部署拉取镜像需要网络（约 860 MB）
```

**Docker 依赖声明（必须同时出现在描述与首次启动引导中，避免「安装后无法直接运行」被判定为缺陷）**

| 场景 | 说明口径 |
|---|---|
| 商店安装的桌面应用（默认） | 打开即用，为 PWA 形态，离线可访问已缓存页面 |
| 完整私有化部署（可选） | 需自行准备 Docker Desktop 4.0+；后端与数据库由使用者自行部署在本机或自有服务器 |
| 首次启动 | 应用内安装引导已提示依赖项与部署入口（见 `docs/deploy/PWA_GUIDE.md`） |

> ⏳ 待确认（P4 提交前）：商店描述中 Docker 依赖的表述口径，须与 `隐私政策`「本地部署型软件」定位保持一致——PWA 商店包仅承载前端界面，业务数据仍在使用者自有环境。

---

## 四、图标与截图对照（Store listing → 素材文件）

### 4.1 商店图标

| 位 | 规格 | 素材文件（仓库内绝对路径） | 来源 |
|---|---|---|---|
| 商店主图标（Store logo） | 300×300 PNG | `D:\OpsCompass\docs\deploy\store-assets\icon-512-300x300.png` | 由 `frontend/public/icons/icon-512.png` 导出 |
| 应用内图标 | 192 / 512 / maskable-512 | `frontend/public/icons/icon-192.png`、`icon-512.png`、`icon-maskable-512.png` | manifest `icons` 已引用 |

### 4.2 商店截图（1–10 张，≥ 1366×768，PNG）

| 序 | 截图内容 | 素材文件 | 关联 URL | manifest 引用 |
|---|---|---|---|---|
| 1 | 登录页 | `D:\OpsCompass\frontend\public\screenshots\login-page-1366x768.png`（副本位于 `output\login-page-1366x768.png`） | `https://opscompass.pages.dev/login` | `/screenshots/login-page-1366x768.png` |
| 2 | 隐私政策页 | `D:\OpsCompass\frontend\public\screenshots\privacy-policy-page-1366x768.png`（副本位于 `output\privacy-policy-page-1366x768.png`） | `https://opscompass.pages.dev/privacy` | `/screenshots/privacy-policy-page-1366x768.png` |
| — | PWABuilder 报告卡 | `output\pwabuilder-reportcard-1366x768.png` | — | **不作为商店截图**，仅作打包校验证据留档 |

> 本次变更已把上表 2 张截图落入 `frontend/public/screenshots/`，并在 `frontend/public/manifest.webmanifest` 的 `screenshots` 字段以 1366×768 / `form_factor: wide` 引用（满足 PWABuilder 报告卡"待补项"）。
> ⏳ 可选补拍（不阻塞提交）：站点为需登录 SPA，`/terms`、`/about`、`/register`、`/dashboard` 均 302 到 `/login`，当前公开可达页仅登录页与隐私页；如后续开放公开页，建议补 1–2 张 1920×1080 截图。
> ⏳ 可选：1920×1080 商店展示图（Store display image），当前未制作。

---

## 五、隐私、合规与分级

### 5.1 隐私政策 URL（必填）

| 字段 | 可直接照抄的值 |
|---|---|
| 隐私政策 URL | `https://opscompass.pages.dev/privacy` |
| 备注 | 请填 canonical 路径（`/privacy`），**不要**填 `/privacy.html`（返回 308 跳转） |
| 隐私政策生效日期 | 2026-10-02（v1.0） |

### 5.2 数据收集声明（提交问卷 / 备注栏可用）

```
本应用为本地部署型软件，业务数据由使用者自行部署的本地数据库存储，开发者不收集、不上传、不查看任何业务数据；应用内不含广告、第三方埋点与遥测 SDK。
应用账号、操作审计日志保存在使用者自有服务端，保留期限可由使用者配置。
AI 能力默认调用本机本地大模型（数据不出设备）；如使用者自行切换为云端 API 模式，数据流向由使用者自行选定的服务商决定。
应用商店版本为 PWA 形态，通过 Microsoft Store 安装后打开；离线缓存仅包含界面静态资源（HTML / 样式 / 图标），不缓存业务接口数据。
```

### 5.3 AI 生成内容声明（AIGC）

| 项目 | 内容 |
|---|---|
| 是否含 AI 生成 / AI 辅助内容 | 是（AI 参谋输出分析结论与建议） |
| 界面标识 | 已在应用界面标注 AI 来源与免责说明 |
| 描述口径 | 保留"AI 参谋"表述，**不做绝对化效果承诺** |
| 商店元数据 | 版本页与描述中不出现"准确率 100%"等承诺性措辞 |

### 5.4 年龄分级（IARC 问卷）

| 问卷项 | 建议答案 |
|---|---|
| 应用类型 | 商务 / 效率工具（非游戏，无需游戏分级问卷） |
| 用户生成内容 / 社交互动 | 无 |
| 暴力、色情、赌博、毒品、粗俗语言 | 无 |
| 是否收集个人信息 | 否（本地部署，见 §5.2） |
| 是否含在线购物 / 内购 | 无 |
| 目标受众 | 企业与运营从业者（成年人），**不面向 13 岁以下儿童** |
| 结果回填 | ⏳ 待 P2 问卷完成后回填 `iarc_rating_id` 至 manifest 与商店元数据 |

---

## 六、支持与联系（Support info）

| 字段 | 可直接照抄的值 | 状态 |
|---|---|---|
| 支持邮箱（Support contact email） | `mxh6789@live.cn` | ✅ |
| 支持 URL（Support URL） | `https://opscompass.pages.dev/` | ✅ 暂用站点首页 |
| 电话（Phone） | 留空 | ✅ 不提供 |
| 官网 / 落地页 | `https://opscompass.pages.dev/` | ✅ |
| 隐私 / 合规专页 | `https://opscompass.pages.dev/privacy` | ✅ |
| 开发者名称 | `BY LAOMENG 网络工作室`（正式值以 §七 为准） | ⏳ 待 P2 回填 |
| 其他联系方式 | `mxh6789@gmail.com` **仅为 Cloudflare 账号标识，不得作为对外联系方式** | ✅ 禁止填入 |

---

## 七、包与提交（Packages）— 待 P2 回填清单

### 7.1 包上载

| 字段 | 值 | 状态 |
|---|---|---|
| 安装包文件 | `运营智脑.msixbundle`（正式包，须重新生成） | ⏳ 待 P2 回填 |
| 当前已有产物 | `OpsCompass.msixbundle`（2.1 MB，**占位身份包，仅可侧载，不可提交**；工作区 output 目录留存） | ✅ 仅本地验证 |
| 架构 | x64（PWABuilder 默认产物） | ✅ |
| 版本 | `1.0.1.0`（占位包内值，正式包版本号按 P2 确认后统一） | ⏳ 待确认 |

### 7.2 三项包标识（必须由 Partner Center 产品标识页复制，严禁沿用占位值）

| Identity 字段 | 当前占位值（不可用） | 正式值 | 状态 |
|---|---|---|---|
| `Package/Identity/Name` | `MyCompany.OpsCompass` | 待回填 | ⏳ P2 |
| `Package/Identity/Publisher` | `CN=3a54a224-05dd-42aa-85bd-3f3c1478fdca` | 待回填 | ⏳ P2 |
| `Package/Properties/PublisherDisplayName` | `My Company Inc` | 待回填 | ⏳ P2 |
| 产品 ID / Store ID（Partner Center 生成） | — | 待回填 | ⏳ P2 |

> 流程：P2 预留产品名称 → 复制上述三项 → 用 PWABuilder 以站点 `https://opscompass.pages.dev/` + 真实标识**重新打包** → 回到本表回填 → 上传提交。

### 7.3 提交前自检

| 检查项 | 判据 |
|---|---|
| 隐私政策 URL 可公网 HTTPS 访问 | `https://opscompass.pages.dev/privacy` 返回 200 |
| 截图 1–10 张、≥ 1366×768 | 当前 2 张，均实测 1366×768 |
| 图标 300×300 已备 | `docs/deploy/store-assets/icon-512-300x300.png` |
| 包内 Identity 与预留名称一致 | 三项标识回填后方可提交 |
| Docker 依赖已在描述中明示 | 见 §3.1 运行说明与 §3.5 |
| AIGC 声明已做 | 见 §5.3 |
| 中英双语文案 | 见 §3.1 / §3.2 |
| manifest `screenshots` 已补 | 本次变更：`frontend/public/screenshots/` + manifest 引用（构建后位于 `frontend/dist/screenshots/`） |

---

## 八、待办汇总（转 P2 / P4）

| 序号 | 待办 | 责任方 | 阻塞级别 |
|---|---|---|---|
| 1 | Partner Center 注册与产品名称预留 | 老板本人（实名） | 硬阻塞 |
| 2 | 回填三项包标识并重新打包 `.msixbundle` | Marvis 重打包 | 硬阻塞 |
| 3 | IARC 分级问卷填写、回填 `iarc_rating_id` | 老板确认，Marvis 记录 | 提交前 |
| 4 | 支持 URL 最终确认（是否建独立支持页） | 老板决策 | 非阻塞 |
| 5 | 可选补拍 1920×1080 截图 / 商店展示图 | Marvis | 非阻塞 |

---
**关联文档**：`docs/deploy/MSSTORE_GUIDE.md`、`docs/deploy/STORE_LISTING.md`、`docs/deploy/PUBLISH_CHECKLIST.md`、`docs/deploy/PWA_GUIDE.md`
