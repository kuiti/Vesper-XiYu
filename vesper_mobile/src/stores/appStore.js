import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api.js'

export const useAppStore = defineStore('app', () => {
  const activeCharacter = ref(null)
  const characterVoice = ref(null)
  const settings = ref({})
  const toast = ref('')
  const toastTimer = ref(null)
  const currentTab = ref('chat')
  const characters = ref([])
  const relationship = ref({ intimacy: 0, trust: 0 })
  const isLoadingChars = ref(false)

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

  async function loadCharacters() {
    isLoadingChars.value = true
    try {
      const res = await api.get('/characters/')
      characters.value = res.data.characters || []
    } catch {} finally {
      isLoadingChars.value = false
    }
  }

  async function activateCharacter(id) {
    try {
      await api.post(`/characters/activate/${id}`)
      await loadActiveCharacter()
      const { useChatStore } = await import('./chatStore.js')
      const chat = useChatStore()
      chat.switchCharacter(id)
      showToast('角色已切换')
    } catch {
      showToast('切换失败')
    }
  }

  async function deleteCharacter(id) {
    try {
      await api.delete(`/characters/${id}`)
      await loadCharacters()
      showToast('已删除')
    } catch {
      showToast('删除失败')
    }
  }

  async function importCharacterJson(jsonStr) {
    const data = JSON.parse(jsonStr)
    await api.post('/characters/import/json', data)
    await loadCharacters()
  }

  async function importCharacterPng(file) {
    const form = new FormData()
    form.append('file', file)
    await api.post('/characters/import/png', form)
    await loadCharacters()
  }

  async function createCharacter(name, description) {
    await api.post('/characters/', { name, description })
    await loadCharacters()
  }

  async function loadRelationship() {
    try {
      const res = await api.get('/relationship/')
      relationship.value = res.data || { intimacy: 0, trust: 0 }
    } catch {}
  }

  function showToast(msg) {
    toast.value = msg
    if (toastTimer.value) clearTimeout(toastTimer.value)
    toastTimer.value = setTimeout(() => { toast.value = '' }, 2500)
  }

  const charName = computed(() => activeCharacter.value?.name || settings.value.ai_name || '夕语')
  const userName = computed(() => settings.value.user_name || '我')
  const avatarUrl = computed(() => {
    if (!activeCharacter.value?.avatar) return ''
    return `/avatars/${activeCharacter.value.avatar}`
  })

  return {
    activeCharacter, characterVoice, settings, toast, currentTab,
    characters, relationship, isLoadingChars, charName, userName, avatarUrl,
    loadSettings, loadActiveCharacter, loadCharacters, activateCharacter,
    deleteCharacter, importCharacterJson, importCharacterPng, createCharacter,
    loadRelationship, showToast,
  }
})
