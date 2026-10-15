/**
 * 动效偏好 composable：尊重系统减弱动效设置
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'

const media = typeof window !== 'undefined' ? window.matchMedia('(prefers-reduced-motion: reduce)') : null

export function useReducedMotion() {
  const reduced = ref(media?.matches ?? false)

  onMounted(() => {
    const handler = (e: MediaQueryListEvent) => {
      reduced.value = e.matches
    }
    media?.addEventListener('change', handler)
    onBeforeUnmount(() => media?.removeEventListener('change', handler))
  })

  return { reduced }
}
