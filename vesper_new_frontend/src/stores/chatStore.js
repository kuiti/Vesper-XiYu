import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api.js'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isStreaming = ref(false)
  const wsReady = ref(false)
  const totalMessages = ref(0)
  const pendingReply = ref('')
  const ws = ref(null)
  const favoriteIds = ref(new Set())
  const sentenceMode = ref('auto')
  const _twQueue = ref([])
  const _twActive = ref(false)

  let _reconnectTimer = null
  let _reconnectAttempts = 0

  function connectWebSocket() {
    if (ws.value && ws.value.readyState <= 1) return
    try {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws.value = new WebSocket(`${proto}://${location.host}/ws/chat`)
    } catch (e) {
      scheduleReconnect()
      return
    }
    ws.value.onopen = () => {
      wsReady.value = true
      _reconnectAttempts = 0
    }
    ws.value.onmessage = (ev) => {
      try { handleWSMessage(JSON.parse(ev.data)) } catch {}
    }
    ws.value.onclose = () => {
      wsReady.value = false
      scheduleReconnect()
    }
    ws.value.onerror = () => {}
  }

  function scheduleReconnect() {
    if (_reconnectTimer) return
    const delay = Math.min(30000, 1000 * Math.pow(2, _reconnectAttempts))
    _reconnectTimer = setTimeout(() => {
      _reconnectTimer = null
      _reconnectAttempts++
      connectWebSocket()
    }, delay)
  }

  function handleWSMessage(data) {
    if (data.type === 'token') {
      pendingReply.value += data.content
    } else if (data.type === 'done') {
      if (pendingReply.value.trim()) {
        messages.value.push({
          role: 'assistant',
          content: pendingReply.value.trim(),
          timestamp: new Date().toISOString(),
          _emotion: data.emotion || null,
        })
      }
      pendingReply.value = ''
      isStreaming.value = false
    } else if (data.type === 'greeting') {
      messages.value.push({
        role: 'assistant',
        content: data.content,
        timestamp: new Date().toISOString(),
        _isGreeting: true,
      })
    } else if (data.type === 'proactive') {
      messages.value.push({
        role: 'assistant',
        content: data.content,
        timestamp: new Date().toISOString(),
        isProactive: true,
      })
    } else if (data.type === 'weather') {
      messages.value.push({
        role: 'assistant',
        content: '__WEATHER__',
        weatherData: data.data,
        timestamp: new Date().toISOString(),
      })
    } else if (data.type === 'surprise') {
      messages.value.push({
        role: 'assistant',
        content: data.content,
        timestamp: new Date().toISOString(),
        isSurprise: true,
      })
    } else if (data.type === 'reroll_start') {
      pendingReply.value = ''
      isStreaming.value = true
    } else if (data.type === 'switched') {
      // 角色切换成功，加载新角色的历史
      loadHistory()
      if (data.first_mes) {
        messages.value.push({
          role: 'assistant',
          content: data.first_mes,
          timestamp: new Date().toISOString(),
          _isGreeting: true,
        })
      }
    } else if (data.type === 'error') {
      isStreaming.value = false
      pendingReply.value = ''
    }
  }

  function sendMessage(text) {
    if (!ws.value || ws.value.readyState !== 1 || !text.trim()) return
    messages.value.push({
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toISOString(),
    })
    totalMessages.value++
    isStreaming.value = true
    pendingReply.value = ''
    ws.value.send(JSON.stringify({ message: text.trim() }))
  }

  async function loadHistory() {
    try {
      const res = await api.get('/chat/history/', { params: { limit: 200 } })
      const data = res.data?.messages || []
      if (Array.isArray(data)) {
        messages.value = data.map(m => ({
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
          id: m.id,
        }))
        totalMessages.value = data.length
      }
    } catch (e) {}
  }

  async function loadFavorites() {
    try {
      const res = await api.get('/favorites/')
      const favs = res.data || []
      favoriteIds.value = new Set(favs.map(f => f.msg_id))
    } catch {}
  }

  async function toggleFavorite(msg) {
    if (!msg?.id) return
    try {
      if (favoriteIds.value.has(msg.id)) {
        await api.delete(`/favorites/${msg.id}`)
        favoriteIds.value.delete(msg.id)
      } else {
        await api.post(`/favorites/${msg.id}`)
        favoriteIds.value.add(msg.id)
      }
    } catch {}
  }

  function switchCharacter(charId) {
    if (!ws.value || ws.value.readyState !== 1) return
    messages.value = []
    totalMessages.value = 0
    pendingReply.value = ''
    isStreaming.value = false
    ws.value.send(JSON.stringify({ type: 'switch_character', character_id: charId }))
  }

  return {
    messages, isStreaming, wsReady, totalMessages, pendingReply,
    favoriteIds, sentenceMode,
    connectWebSocket, switchCharacter,
    sendMessage, loadHistory, loadFavorites, toggleFavorite,
  }
})
