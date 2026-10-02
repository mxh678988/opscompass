---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 350ab7144af9618434cdce7bfa6d84e8_2504c994be5b11f1887c525400de85a5
    ReservedCode1: 8uorGbPFIuVnGRxdMZRLLPs8/ZYWKs8rjd4VCMfeOcmMmk10sPR1b2mB1+IgPR39Rfxrs73ZFvAU0b8eJGeRzSTyvxau3+0LRW09ZGVCwOl9RGfPa12aLXGTgShjCtwv617ks1xYhPZfmwIoHff48SLxNBWbIXguwv7rnQvm7Z3/4ilBYXy4SK+K+cw=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 350ab7144af9618434cdce7bfa6d84e8_2504c994be5b11f1887c525400de85a5
    ReservedCode2: 8uorGbPFIuVnGRxdMZRLLPs8/ZYWKs8rjd4VCMfeOcmMmk10sPR1b2mB1+IgPR39Rfxrs73ZFvAU0b8eJGeRzSTyvxau3+0LRW09ZGVCwOl9RGfPa12aLXGTgShjCtwv617ks1xYhPZfmwIoHff48SLxNBWbIXguwv7rnQvm7Z3/4ilBYXy4SK+K+cw=
---

# 运营智脑 PWA 站点托管方案（Cloudflare Pages）

> 生成日期：2026-10-02 · 关联：`docs/deploy/PWA_GUIDE.md`、`docs/deploy/MSSTORE_GUIDE.md`
> 用途：为 Microsoft Store 上架与三端移动端提供**公网 HTTPS 站点**与**隐私政策 URL**。

## 一、为什么选 Cloudflare Pages

| 维度 | 说明 |
|---|---|
| 费用 | 免费（每月 500 次构建、无限请求与带宽） |
| 备案 | 无需 ICP 备案，`*.pages.dev` 自带 HTTPS 证书 |
| 仓库 | 支持连接**私有** GitHub 仓库（免费版即可） |
| 审核可达性 | 微软商店审核服务器位于境外，访问 `pages.dev` 无障碍 |
| 回滚 | 每次部署生成独立版本，可一键回滚 |

## 二、路线 A（推荐）：本地构建 + Wrangler 直传

不把代码交给 Cloudflare 构建，产物由本机上传，构建链路可控。

### 1. 前置准备

1. 注册 / 登录 Cloudflare：https://dash.cloudflare.com/sign-up （邮箱即可，免费）
2. 取得 **Account ID**：Dashboard 右侧栏 → Account ID
3. 创建 **API Token**：My Profile → API Tokens → Create Token → 模板选 **Edit Cloudflare Workers** 或自定义，权限需含 **Account → Cloudflare Pages → Edit**
4. 本机设置环境变量（**不要写入脚本或提交仓库**）：

```powershell
$env:CLOUDFLARE_API_TOKEN  = "<你的 API Token>"
$env:CLOUDFLARE_ACCOUNT_ID = "<你的 Account ID>"
```

### 2. 一键发布

```powershell
cd D:\OpsCompass\deploy\scripts
.\deploy-cloudflare-pages.ps1
```

脚本行为：构建前端 → 校验 `manifest.webmanifest` 存在 → 创建 Pages 项目（已存在则跳过）→ 上传 `frontend/dist`。

### 3. 发布后验证

| 项 | 期望结果 |
|---|---|
| `https://opscompass.pages.dev/` | 正常打开登录页，地址栏出现安装图标 |
| `https://opscompass.pages.dev/privacy` | 隐私政策页正常渲染（`/privacy.html` 会 308 跳转至此，亦算通过） |
| `https://opscompass.pages.dev/manifest.webmanifest` | 返回 JSON，`Content-Type` 正常 |
| `https://opscompass.pages.dev/sw.js` | 返回 JS，DevTools → Application 显示 SW activated |

## 三、路线 B：Dashboard 连接私有仓库（自动构建）

仓库为 monorepo，需在项目设置中指定：

| 配置项 | 值 |
|---|---|
| Project name | opscompass |
| Production branch | main |
| Framework preset | None / Vite |
| Root directory | frontend |
| Build command | npm ci && npm run build |
| Build output directory | dist |

首次连接需在 Cloudflare 侧完成 GitHub OAuth 授权。私有仓库推送后自动触发部署。

## 四、隐私政策 URL 交付

商店审核需填写**公网可访问**的隐私政策 URL：

```
https://opscompass.pages.dev/privacy
```

> ⚠️ Pages 默认启用 clean URL：访问 `/privacy.html` 会返回 **308** 跳转到 `/privacy`。商店后台请填 canonical 地址（`/privacy`），虽 308 通常也能被审核接受，但直接填最终地址更稳。

> 联系邮箱已填写为 `mxh6789@live.cn`（2026-10-02 更正），可直接用于商店审核提交。
>
> 注：`mxh6789@gmail.com` 是 Cloudflare 账号标识（非联系邮箱），请勿再填入隐私政策的联系邮箱栏位；
> `CLOUDFLARE_ACCOUNT_ID` 与 `CLOUDFLARE_API_TOKEN` 仍需从 Cloudflare 控制台获取后以环境变量提供。

## 五、自定义域名（可选，后续）

1. 域名可托管在 Cloudflare（免费 DNS）或原注册商；
2. Pages 项目 → Custom domains → 添加域名（如 `ops.laomeng.xx`）；
3. HTTPS 证书由 Cloudflare 自动签发，无需备案（服务器在境外）。

## 六、风险与注意事项

| 风险 | 应对 |
|---|---|
| API Token 泄露 | 只授予 Pages:Edit 最小权限；仅通过环境变量注入，禁止写入脚本与仓库 |
| Service Worker 缓存旧版本 | 站点更新后 SW 缓存名随版本号变化，旧缓存自动清理；必要时 DevTools → Application → Unregister 强制刷新 |
| API 地址混用 | 公网站点为纯前端展示（PWA/MSIX 场景），后端仍为本地 Docker；公网访问时 `/api` 请求会失败，属预期 |
| 免费额度 | 500 次构建/月，直传路线基本不消耗构建次数 |

---
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
