import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api.js'

export const useAppStore = defineStore('app', () => {
  const activeView = ref('chat')
  const activeCharacter = ref(null)
  const characterVoice = ref(null)
  const settings = ref({})
  const showCmdPalette = ref(false)
  const toast = ref('')
  const toastTimer = ref(null)

  async function loadSettings() {
    try {
      const res = await api.get('/settings/')
      settings.value = res.data || {}
    } catch {}
  }

  async function loadActiveCharacter() {
    try {
      const res = await api.get('/characters/active')
      activeCharacter.value = res.data?.character || null
      characterVoice.value = activeCharacter.value?.voice || null
    } catch {
      activeCharacter.value = null
      characterVoice.value = null
    }
  }

  async function activateCharacter(id) {
    try {
      await api.post(`/characters/activate/${id}`)
      await loadActiveCharacter()

      // 通过 WebSocket 消息通知服务端切换角色（不断开连接）
      const { useChatStore } = await import('./chatStore.js')
      const chat = useChatStore()
      chat.switchCharacter(id)
      showToast('角色已切换')
    } catch (e) {
      showToast('切换失败')
    }
  }

  function showToast(msg) {
    toast.value = msg
    if (toastTimer.value) clearTimeout(toastTimer.value)
    toastTimer.value = setTimeout(() => { toast.value = '' }, 2500)
  }

  function toggleCmdPalette() {
    showCmdPalette.value = !showCmdPalette.value
  }

  return {
    activeView, activeCharacter, characterVoice, settings, showCmdPalette, toast,
    loadSettings, loadActiveCharacter, activateCharacter, showToast, toggleCmdPalette,
  }
})
