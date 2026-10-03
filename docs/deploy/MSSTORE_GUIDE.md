---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_9b019f39be4811f1887c525400de85a5
    ReservedCode1: NA7mUIFpC0Uzg78YIZS5Db+mI2c1rDR631BDVG8TjTs6TMMNG3KVO8ArmcUT8OtvbKCext1mGsqM5ggVN8tXeCzcGNcjyausfnyJrSNOil8EnTW1ztsNNvfJBAj+dMeBMAssAaz1EAuJoRKkcGer95oB6cfpt8ASHdxrPGR0qGlX1N4JfoaHCGlfU2c=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_9b019f39be4811f1887c525400de85a5
    ReservedCode2: NA7mUIFpC0Uzg78YIZS5Db+mI2c1rDR631BDVG8TjTs6TMMNG3KVO8ArmcUT8OtvbKCext1mGsqM5ggVN8tXeCzcGNcjyausfnyJrSNOil8EnTW1ztsNNvfJBAj+dMeBMAssAaz1EAuJoRKkcGer95oB6cfpt8ASHdxrPGR0qGlX1N4JfoaHCGlfU2c=
---

# 运营智脑 OpsCompass · Microsoft Store 上架方案

> 生成时间：2026-10-02 | 最后更新：2026-10-03（回填 P2 真实产品标识与 P3 正式包重打结论） | 适用版本：v0.10.1+ | 依据：微软 2025-09-11 开发者政策调整

## 一、政策要点（已联网核实）

| 项目 | 结论 |
|---|---|
| 个人开发者费用 | **免费**（原 $19 注册费取消，应用签名与二进制托管由微软承担） |
| 覆盖区域 | 全球近 200 个市场 |
| 支持应用类型 | Win32（含 .NET WPF / WinForms）、UWP、PWA、.NET MAUI、Electron |
| 提交格式 | 打包为 MSIX，提交 `.msixbundle` |
| 内购抽成 | 非游戏应用自建内购系统 **0 抽成** |
| 开发者账号 | 微软账户 + Partner Center；企业主体可另注册企业账号（$99） |
| 身份验证 | 政府证件扫描 + 自拍照，全程约数分钟 |
| 审核周期 | 1-5 个工作日 |
| 商店规模 | 月活跃用户约 2.5 亿 |

来源：微软官方公告与 Microsoft Learn 文档，The Verge / BleepingComputer / iThome 2025-09 报道。

## 二、两条上架路线

| 路线 | 适用场景 | 产物 | 优点 | 代价 |
|---|---|---|---|---|
| **A. PWA → MSIX** | 已有 Web 前端且可补齐 PWA 能力 | `.msixbundle` | 复用现有前端，改动最小；与 `docs/MOBILE_PLAN.md` 的 PWA 先行路线同源 | 需补齐 manifest 与 Service Worker 离线能力 |
| **B. Win32 → MSIX** | 桌面安装包（exe / 脚本型） | `.msixbundle` | 保留原生安装体验 | 需 MSIX Packaging Tool 工具链；Docker 依赖需在应用内引导处理 |

**推荐路线：A**。与移动端 PWA 先行策略一致，边际成本最低。

## 三、上架操作步骤

1. **注册**：登录 Partner Center（个人微软账户）→ 注册 Windows 开发者计划 → 完成身份验证（证件 + 自拍）
2. **预约产品**：工作区 → 应用与游戏 → 新产物 → **MSIX 或 PWA 应用** → 输入预订单名称 → 预留产品名称 ✅ 已完成（2026-10-03，名称「运营智脑 OpsCompass」，Store ID `9NVPQCMPZGLN`）
3. **记录标识**：产品管理 → 产品标识，复制并保存三项 ✅ 已完成，真实值见 5.2：
   - Package Identity Name（套件标识符）
   - Publisher ID（发布者标识）
   - Publisher Display Name（发布者显示名称）
4. **打包**：用 PWABuilder 输入站点 URL + 上述标识 → 生成 `.msixbundle`（新版 Windows）与 `.classic.appxbundle`（旧版兼容）
5. **提交**：上传安装包 → 填写商店页面（隐私政策 URL、截图、分类、描述）→ 提交审核
6. **发布**：审核通过后自动上线，签名与分发由微软完成，无需自建 CDN

## 四、前置改造要点（OpsCompass 专用）

| 事项 | 要求 |
|---|---|
| PWA 能力（路线 A） | `manifest.json`（名称 / 图标 / 主题色）、Service Worker 离线缓存、HTTPS、可安装提示 |
| 隐私政策页 | ✅ 已托管：`https://opscompass.pages.dev/privacy`（Cloudflare Pages，2026-10-03 上线） |
| 商店素材 | 应用图标（多尺寸）、截图（桌面端 1366×768 起）、中英文描述文案；文案与素材清单已备 → [STORE_LISTING.md](./STORE_LISTING.md) |
| 数据合规声明 | 本地部署型软件，需在商店页面声明不收集用户数据 |
| 运行时依赖 | 应用运行时仍依赖 Docker Desktop，需在商店描述与首次启动引导中明示 |

## 五、排期与依赖

| 阶段 | 内容 | 依赖 |
|---|---|---|
| P0 | ✅ **已完成（2026-10-02）** PWA 能力补齐（manifest + Service Worker + 图标 + 离线页 + 应用内安装引导） | 落地清单见 `docs/deploy/PWA_GUIDE.md` |
| P1 | 隐私政策静态页托管 | ✅ 已完成（2026-10-03，Cloudflare Pages，见 `CLOUDFLARE_PAGES_GUIDE.md`） |
| P2 | ✅ **已完成（2026-10-03）**：Partner Center 账号实名完成，产品「运营智脑 OpsCompass」预留成功（Store ID `9NVPQCMPZGLN`），三项真实标识已读回（见 5.2） | 老板本人实名 + 微软账户 |
| P3 | ✅ **已完成（2026-10-03）**：PWABuilder 可打包性校验全通过；占位包与**真实标识正式包**均已产出（正式包 `OpsCompass-9NVPQCMPZGLN.msixbundle`，见 5.2）；商店截图已采集（实测结论见 5.1） | PWABuilder |
| P4 | ⬜ **待启动**：上传正式包 `OpsCompass-9NVPQCMPZGLN.msixbundle` 并提交审核（商店页面信息 + 商店截图 + 隐私 URL + IARC 分级问卷）；**须在名称保留截止约 2027-01-03 前完成提交** | 文案已备（`STORE_LISTING.md`）；正式包已就绪（见 5.2）；产品为草稿态，提交入口 `products/9NVPQCMPZGLN/overview` |

工作量估算：约 **3 ~ 5 人天**（不含审核等待），现金成本 **0 元**（个人开发者免费）。

### 5.1 P3 实测结论（2026-10-03）

**校验（PWABuilder Report Card，站点 `https://opscompass.pages.dev/`）**

| 维度 | 结论 |
|---|---|
| 可安装性 / 可打包性 | ✅ 通过（Manifest 得分 28/46，Required 字段齐备） |
| Manifest 必备字段 | ✅ `name` / `short_name` / `start_url` / `scope` / `display=standalone` / 主题色 / 背景色 / 图标均存在 |
| 图标尺寸 | ✅ 实测与声明一致：192×192、512×512、maskable 512×512 |
| Service Worker / 离线 | ✅ 实测 1 条 active 注册（`/sw.js`，scope 为站点根），Cache Storage 含 `opscompass-static-v0.10.1` |
| HTTPS / 安全上下文 | ✅ Cloudflare Pages 提供有效 HTTPS |
| 待补项 | ⚠️ 均为**可选增强项，不阻塞打包**：`screenshots`、`launch_handler`（含 `handle_links` / `prefer_related_applications`）已于 2026-10-03 补齐并随 `frontend/public/manifest.webmanifest` 落地，构建后位于 `frontend/dist/screenshots/`；`related_applications`、`iarc_rating_id` 及 `scope_extensions` / `file_handlers` / `share_target` / `widgets` 等推荐能力项仍未配 |

**打包产出（首轮占位身份包，仅可侧载；真实标识正式包见 5.2）**

- 已下载 Windows 包，内含 `运营智脑.msixbundle`、`.sideload.msix`、`.classic.appxbundle`、`install.ps1`、`utils\pwainstaller.exe`。
- 包内 Identity 三项**全部为 PWABuilder 预填占位值**（页面明确标注需从 Partner Center 获取）：

| 字段 | 包内实际值（占位） | 来源 |
|---|---|---|
| Package/Identity/Name | `MyCompany.OpsCompass` | Partner Center → 产品标识 |
| Package/Identity/Publisher | `CN=3a54a224-05dd-42aa-85bd-3f3c1478fdca` | Partner Center → 产品标识 |
| Package/Properties/PublisherDisplayName | `My Company Inc` | Partner Center → 产品标识 |
| Version | `1.0.1.0` | 自定 |

> **结论**：该包为**占位身份包**，仅可用于本地侧载验证（配合 `install.ps1`），**不可直接提交 Microsoft Store**。正式上架须先完成 P2（Partner Center 预留产品名称），回填上述三项真实标识后**重新打包**——P2 与重打包均已于 2026-10-03 完成，正式包见 5.2。PWABuilder 免登录即可打包，本次流程未出现登录墙，故无账号阻断。

**商店截图（1366×768，已核验实际像素）**

| 文件 | 页面 |
|---|---|
| `login-page-1366x768.png` | `https://opscompass.pages.dev/login` |
| `privacy-policy-page-1366x768.png` | `https://opscompass.pages.dev/privacy` |
| `pwabuilder-reportcard-1366x768.png` | PWABuilder 报告卡（校验证据） |

> 站点为需登录的 SPA：`/terms`、`/about`、`/register`、`/dashboard` 均重定向至 `/login?redirect=...`，当前公开可达页仅 `/login` 与 `/privacy`，故商店截图暂为 2 张（商店要求 1–10 张，已达标下限；建议后续补 1 张 1920×1080 或更多公开页截图）。
> 2026-10-03 变更：两张截图已复制进仓库 `frontend/public/screenshots/`，并在 `frontend/public/manifest.webmanifest` 的 `screenshots` 字段以 1366×768 / `form_factor: wide` 引用（提审表单填写稿见 `docs/deploy/MSSTORE_SUBMISSION_FORM.md`）。

**P3 遗留阻断点（转入 P4）**：① 三项真实包标识 —— ✅ **已解除**，P2 已取得并据此重打正式包（见 5.2）；② `iarc_rating_id` 等可选增强项仍待 P4 问卷回填。`screenshots` 与 `launch_handler` 已于 2026-10-03 补齐，不再列为遗留项。

### 5.2 P2 产品预留与正式包实测结论（2026-10-03）

**P2 产品预留与真实标识（读自 Partner Center，未编造任何值）**

| 项目 | 真实值 |
|---|---|
| 账号 | `mxh6789@live.cn`（已完成实名；Partner Center 显示名 `xianghui`） |
| 预留产品名称 | 「运营智脑 OpsCompass」（一次通过，未启用备选名「OpsCompass 运营智脑」「OpsCompass」） |
| Store ID | `9NVPQCMPZGLN` |
| 产品状态 | 草稿（未提交认证、未配置定价） |
| 名称保留截止 | 约 **2027-01-03**（页面原文：须在三个月内提交，否则丢失保留的名称） |
| Store URL | `https://apps.microsoft.com/detail/9NVPQCMPZGLN` |
| `Package/Identity/Name` | `LAOMENG.OpsCompass` |
| `Package/Identity/Publisher` | `CN=A65E517F-EADC-4803-B9C4-E753441561FC` |
| `Package/Properties/PublisherDisplayName` | `LAOMENG 网络工作室` |
| Package Family Name（PFN） | `LAOMENG.OpsCompass_9wp8gzp9rz5xa` |

> 同账号下原已有 1 个产品「AI短剧工厂」（已上架，240 个市场）；登录由用户手动完成（含 MFA），未代填任何凭据。

**正式包重打与核验（PWABuilder + 真实标识）**

| 产物 | 大小 | 核验结果 |
|---|---|---|
| `OpsCompass-9NVPQCMPZGLN.msixbundle` | 2,175.5 KB | `Identity` 的 Name / Publisher / Version `1.0.1.0` 与 `Properties/PublisherDisplayName` 四项与 Partner Center 真实值完全一致，**可直接用于 P4 提交** |
| `OpsCompass-9NVPQCMPZGLN.sideload.msix` | 2,173.8 KB | 身份与显示名匹配（Publisher 含 OID 后缀） |
| `OpsCompass-9NVPQCMPZGLN.classic.appxbundle` | 2,217.7 KB | 身份与显示名匹配；Version 为 `1.0.0.0`（经典桌面封装独立版本号） |

> 核验方式：解包读取包内 `AppxManifest.xml`（核验副本见会话 output 目录 `OpsCompass-9NVPQCMPZGLN-AppxManifest.xml`）。PWABuilder 全程未要求登录，无账号阻断。
> 命名注意：PWABuilder 表单版本号只接受三段格式，填 `1.0.1` 后自动补零为 `1.0.1.0`。
> 提审表单回填稿见 `docs/deploy/MSSTORE_SUBMISSION_FORM.md` §七（§7.0 P2 完成记录 / §7.1 包 / §7.2 三项标识）。

## 六、风险与大坑

| 风险 | 应对 |
|---|---|
| 隐私政策页无法公网访问 → 审核被拒 | P1 阶段先完成托管再提交 |
| PWA 离线能力不足 → 审核被拒 | 补齐 Service Worker，保证离线可打开基础页 |
| Docker 依赖导致「安装后无法直接运行」被判定为缺陷 | 商店页面与首次启动引导明确说明依赖 Docker Desktop |
| 私有仓库无法直接作为商店安装源 | 商店分发走微软托管，不依赖仓库；PWA 站点需公网可访问 |

## 七、与其它规划的关系

- 与 `docs/MOBILE_PLAN.md`：共用 PWA 先行路线，一套前端同时覆盖 Windows 商店与三端移动端。
- 与 `docs/deploy/PUBLISH_CHECKLIST.md`：Windows 商店项目状态由「规划中（免注册费）」推进为「S1-P2/P3 已完成、待 P4 提交」（产品预留 Store ID `9NVPQCMPZGLN`，正式包已产出）。

---
**关联文档**：`docs/deploy/PUBLISH_CHECKLIST.md`、`docs/MOBILE_PLAN.md`、`docs/deploy/LOCAL_INSTALLER_GUIDE.md`
*（内容由AI生成，仅供参考）*
