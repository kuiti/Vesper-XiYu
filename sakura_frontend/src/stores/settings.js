// stores/settings.js — 配置状态
import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api.js'

export const useSettingsStore = defineStore('settings', () => {
  const allSettings = ref({})
  const aiName = ref('佐仓')
  const userName = ref('')
  const theme = ref('dark')

  async function load() {
    try {
      const res = await api.get('/settings/')
      const s = res.data
      allSettings.value = s
      aiName.value = s.ai_name || '佐仓'
      userName.value = s.user_name || ''
      theme.value = s.theme || 'dark'
    } catch (e) { console.error('[settings] load failed', e) }
  }

  function update(key, value) {
    allSettings.value[key] = value
    if (key === 'ai_name') aiName.value = value
    if (key === 'user_name') userName.value = value
    if (key === 'theme') theme.value = value
  }

  return { allSettings, aiName, userName, theme, load, update }
})
