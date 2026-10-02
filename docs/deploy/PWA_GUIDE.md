# 运营智脑 PWA 能力说明（P0 已落地）

> 生成日期：2026-10-02 · 对应版本：v0.10.1 · 关联文档：`docs/deploy/MSSTORE_GUIDE.md`、`docs/MOBILE_PLAN.md`

## 一、落地文件清单

| 类别 | 文件 | 说明 |
|---|---|---|
| 应用清单 | `frontend/public/manifest.webmanifest` | 名称/短名/主题色/背景色/standalone/快捷入口 3 个 |
| 图标 | `frontend/public/icons/icon-192.png` | 标准图标 192×192 |
| 图标 | `frontend/public/icons/icon-512.png` | 标准图标 512×512 |
| 图标 | `frontend/public/icons/icon-maskable-512.png` | 蒙版图标（内容缩进 16% 安全区） |
| 图标 | `frontend/public/icons/apple-touch-icon.png` | iOS 主屏图标 180×180（不透明） |
| 图标 | `frontend/public/icons/favicon-32.png` | 32×32 备用图标 |
| 离线脚本 | `frontend/public/sw.js` | Service Worker：预缓存 + 分策略缓存 + 旧版本清理 |
| 离线页 | `frontend/public/offline.html` | 断网且无缓存时兜底页（含 Docker 依赖提示） |
| 隐私页 | `frontend/public/privacy.html` | 静态隐私政策页（商店审核引用；联系邮箱待补充） |
| 入口改造 | `frontend/index.html` | 注入 manifest / apple-touch-icon / PWA meta |
| 注册逻辑 | `frontend/src/main.ts` | 仅生产构建注册 SW，含更新检测与自动激活 |

## 二、缓存策略

| 请求类型 | 策略 | 说明 |
|---|---|---|
| 导航请求（HTML） | network-first | 在线取最新页面；断网回退缓存的 app shell，再回退 offline.html |
| 同源静态资源（`/assets/`、`/icons/`、css/js/图片/字体） | stale-while-revalidate | 先返回缓存保证秒开，后台静默更新 |
| `/api/*` 与跨域请求 | 不拦截 | 业务数据与鉴权响应永不进缓存，避免脏数据 |
| 非 GET 请求 | 不拦截 | 写操作全部直达服务端 |

缓存名：`opscompass-static-v0.10.1`；`activate` 阶段自动清理同前缀旧版本缓存。

## 三、更新机制

1. 仅生产构建（`import.meta.env.PROD`）注册 Service Worker，开发环境不注册，避免干扰 HMR。
2. 页面已被旧版本 SW 接管时，检测到新版本安装完成即发送 `SKIP_WAITING`，`controllerchange` 后自动刷新一次。
3. 运行期间每小时调用一次 `registration.update()` 检查新版本。

## 四、本地验证方法

```powershell
cd D:\OpsCompass\frontend
npm run build
npm run preview
```

Chrome / Edge 打开 `http://localhost:4173` → F12 → Application 面板：

- Manifest：应显示名称「运营智脑 OpsCompass」、图标、standalone；
- Service Workers：应显示 `/sw.js` 状态 activated；
- Cache Storage：应存在 `opscompass-static-v0.10.1`；
- 地址栏出现「安装」图标即表示可安装；
- Network 面板切 Offline 后刷新，应能打开离线页或缓存的 app shell。

## 五、与商店 / 移动端的关系

- Microsoft Store：PWA → MSIX 路线的前置条件「manifest + Service Worker 离线能力 + HTTPS」已具备，剩余前置为**公网 HTTPS 托管**（见 MSSTORE_GUIDE 的 P1）。
- 移动端三端：PWA 先行路线共用本套 manifest 与 SW，可直接复用，无需重复开发。
- 待办（P1）：将 `privacy.html` 与 dist 静态站点托管到公网 HTTPS 域名，并把 URL 填入商店后台。

---
*（内容由AI生成，仅供参考）*