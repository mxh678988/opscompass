import { onMounted, ref } from 'vue'

/**
 * beforeinstallprompt 事件（Chromium 私有事件，TS 标准类型未覆盖）
 */
interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[]
  prompt(): Promise<void>
  readonly userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

const DISMISS_KEY = 'opscompass.pwa.install.dismissed'

/**
 * PWA 安装引导：捕获浏览器安装提示事件，暴露「可安装」状态与触发安装能力。
 * - 仅在浏览器判定可安装、且用户未忽略过时展示
 * - 已处于独立窗口（standalone）运行时不再展示
 */
export function usePwaInstall() {
  const canInstall = ref(false)
  const visible = ref(false)
  const installed = ref(false)
  let deferred: BeforeInstallPromptEvent | null = null

  function isStandalone(): boolean {
    if (window.matchMedia?.('(display-mode: standalone)').matches) return true
    // iOS Safari 私有属性
    return (window.navigator as unknown as { standalone?: boolean }).standalone === true
  }

  function readDismissed(): boolean {
    try {
      return window.localStorage.getItem(DISMISS_KEY) === '1'
    } catch {
      // 隐私模式下 localStorage 不可用，按未忽略处理
      return false
    }
  }

  function dismiss(): void {
    visible.value = false
    canInstall.value = false
    try {
      window.localStorage.setItem(DISMISS_KEY, '1')
    } catch {
      /* 忽略写入失败 */
    }
  }

  async function install(): Promise<void> {
    if (!deferred) return
    const promptEvent = deferred
    deferred = null
    canInstall.value = false
    visible.value = false
    await promptEvent.prompt()
    const choice = await promptEvent.userChoice
    if (choice.outcome === 'accepted') installed.value = true
  }

  onMounted(() => {
    if (isStandalone() || readDismissed()) return

    window.addEventListener('beforeinstallprompt', (event) => {
      // 阻止浏览器默认迷你信息栏，改由应用内引导条承载
      event.preventDefault()
      deferred = event as BeforeInstallPromptEvent
      canInstall.value = true
      visible.value = true
    })

    window.addEventListener('appinstalled', () => {
      deferred = null
      canInstall.value = false
      visible.value = false
      installed.value = true
    })
  })

  return { canInstall, visible, installed, install, dismiss }
}
