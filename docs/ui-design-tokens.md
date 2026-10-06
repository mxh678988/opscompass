
# 前端设计令牌规范（P4）

> 适用产品：运营智脑（让数据自动做出最优决策）
> 落地版本：0.7.0　｜　令牌定义位置：`frontend/src/styles/main.css`

## 1. 原则

1. **零硬编码**：所有页面样式中的颜色、圆角、阴影、间距、过渡必须引用设计令牌变量，禁止书写 `#xxxxxx`、`10px` 之类的裸值（渐变装饰层等特殊视觉除外）。
2. **单点定义**：令牌只在 `main.css` 的 `:root` 中定义一次，改主题只需改一处。
3. **令牌优先于局部覆盖**：新增页面先复用全局基线（表格 / 按钮 / 输入框），再写必要的 scoped 样式。

## 2. 令牌清单

### 2.1 品牌色

| 令牌 | 值 | 用途 |
|---|---|---|
| `--color-primary` | `#2563eb` | 主色：主按钮、链接、强调、图表主色 |
| `--color-primary-hover` | `#1d4ed8` | 主色 hover / 激活态 |
| `--color-primary-light` | `#eff6ff` | 主色浅底：导航 active、标签、选中态背景 |
| `--color-primary-border` | `#bfdbfe` | 主色浅边框：卡片 hover、按钮 hover 描边 |
| `--color-focus` | `#3b82f6` | 输入框聚焦边框 |

语义色（各含 `-light` 浅底与 `-border` 浅边框）：`--color-success`（`#16a34a`）、`--color-warning`（`#d97706`）、`--color-error`（`#dc2626`）。

### 2.2 文字

| 令牌 | 值 | 用途 |
|---|---|---|
| `--color-text` | `#1f2937` | 正文、标题 |
| `--color-text-secondary` | `#4b5563` | 次要说明、表格表头 |
| `--color-text-muted` | `#9ca3af` | 占位、提示、空态 |
| `--color-text-link` | `#2563eb` | 链接 |

### 2.3 背景与边框

| 令牌 | 值 | 用途 |
|---|---|---|
| `--color-bg` | `#ffffff` | 页面 / 卡片底色、深色按钮上的文字 |
| `--color-bg-subtle` | `#f8fafc` | 次级底色：标签、代码块、表头 |
| `--color-bg-hover` | `#f1f5f9` | 表格行 hover、列表 hover |
| `--color-border` | `#e5e7eb` | 常规边框 |
| `--color-border-light` | `#f1f5f9` | 分隔线、卡片内细分隔 |

### 2.4 阴影 / 圆角 / 间距 / 动画

| 类别 | 令牌 |
|---|---|
| 阴影 | `--shadow-sm`（1px 轻投影）、`--shadow-md`（卡片常规）、`--shadow-card`（卡片 hover 抬升） |
| 圆角 | `--radius-sm`(6px)、`--radius-md`(8px)、`--radius-lg`(12px)、`--radius-xl`(16px)、`--radius-full`(9999px) |
| 间距 | `--space-1`(4) `--space-2`(8) `--space-3`(12) `--space-4`(16) `--space-5`(20) `--space-6`(24) `--space-8`(32) `--space-10`(40) `--space-12`(48) `--space-16`(64) |
| 动画 | `--transition-fast`(150ms)、`--transition-base`(200ms)、`--transition-slow`(300ms) |
| 字体 | `--font-sans`、`--font-mono` |

## 3. 页面级统一约定

| 约定项 | 规范 |
|---|---|
| 页面容器 | `padding: 32px` + `max-width: 1400px` + `margin: 0 auto` |
| 副标题 `.subtitle` | `color: var(--color-text-secondary)`，`font-size: 14px`，下间距 24px |
| 面板 `.panel` | `1px solid var(--color-border)` + `var(--radius-lg)` + `padding: 20px` + `background: var(--color-bg)`，hover 时描边转 `--color-primary-border` |
| 面板标题 `.panel h2` | 15px / 600 字重 / `var(--color-text)` |
| 表格 | 复用全局基线；行 hover 底色 `--color-bg-hover` |
| 标签 `.tag` | 圆角 `10px`、12px、600 字重；语义色由 `.tag.ok/.warn/.bad/.muted` 承载 |
| 主按钮 `button.primary` | 底色 `--color-primary`，hover 转 `--color-primary-hover` 并带 `rgba(37,99,235,0.22)` 投影 |
| 输入框聚焦 | 全局基线已提供 `--color-focus` 描边 + `0 0 0 3px rgba(59,130,246,0.12)` 光环 |
| 响应式 | 768px / 480px 两级断点，收敛为单列 |

## 4. 新增页面 checklist

- [ ] 未在 scoped 样式中出现裸色值（`#` 开头的十六进制）
- [ ] 容器使用统一 `max-width: 1400px` 居中
- [ ] 面板 / 表格 / 按钮 / 标签复用全局基线或页面统一约定
- [ ] 交互态（hover / focus / disabled）齐全，过渡使用 `--transition-fast`
- [ ] 补 768px / 480px 断点适配

*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
