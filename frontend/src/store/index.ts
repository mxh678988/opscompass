import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 全局应用状态 */
export const useAppStore = defineStore('app', () => {
  const title = ref(import.meta.env.VITE_APP_TITLE || '运营智脑')
  const loading = ref(false)

  function setLoading(value: boolean) {
    loading.value = value
  }

  return { title, loading, setLoading }
})
