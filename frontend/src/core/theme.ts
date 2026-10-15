/**
 * 主题换肤机制（迭代2 · UI 美化与体验升级）
 * - 三态模式：light / dark / system（跟随系统）
 * - 持久化：localStorage `opscompass-theme`
 * - 落地方式：html[data-theme]，令牌定义在 styles/main.css
 */
export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'opscompass-theme'
const media = window.matchMedia('(prefers-color-scheme: dark)')

/** 解析系统偏好对应的实际主题 */
export function systemTheme(): 'light' | 'dark' {
  return media.matches ? 'dark' : 'light'
}

/** 读取当前保存的模式（无保存记录返回 system） */
export function loadThemeMode(): ThemeMode {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw === 'light' || raw === 'dark' || raw === 'system' ? raw : 'system'
}

/** 应用主题：写 html[data-theme]（system 时按系统偏好落地） */
export function applyTheme(mode: ThemeMode): void {
  const resolved = mode === 'system' ? systemTheme() : mode
  document.documentElement.dataset.theme = resolved
  document.documentElement.style.colorScheme = resolved
}

/** 保存模式并应用 */
export function setThemeMode(mode: ThemeMode): void {
  localStorage.setItem(STORAGE_KEY, mode)
  applyTheme(mode)
}

/** 监听系统偏好变化（仅在 system 模式下生效） */
export function watchSystemTheme(): () => void {
  const handler = () => {
    if (loadThemeMode() === 'system') applyTheme('system')
  }
  media.addEventListener('change', handler)
  return () => media.removeEventListener('change', handler)
}

/** 初始化：立即落地一次并挂监听（在 main.ts 或 App 挂载时调用） */
export function initTheme(): void {
  applyTheme(loadThemeMode())
  watchSystemTheme()
}
