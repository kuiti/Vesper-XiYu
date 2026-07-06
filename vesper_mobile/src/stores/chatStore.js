import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api, { getWsUrl } from '../api.js'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isStreaming = ref(false)
  const wsReady = ref(false)
  const totalMessages = ref(0)
  const pendingReply = ref('')
  const ws = ref(null)
  const favoriteIds = ref(new Set())
  const sessions = ref([])
  const activeSessionId = ref(null)
  const isLoading = ref(false)
  const error = ref(null)

  let _reconnectTimer = null
  let _reconnectAttempts = 0

  function connectWebSocket() {
    if (ws.value && ws.value.readyState <= 1) return
    try {
      ws.value = new WebSocket(getWsUrl())
    } catch {
      scheduleReconnect()
      return
    }
    ws.value.onopen = () => {
      wsReady.value = true
      _reconnectAttempts = 0
      error.value = null
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
      error.value = data.content || '发生错误'
    }
  }

  function sendMessage(text, imageBase64) {
    if (!ws.value || ws.value.readyState !== 1) return
    const trimmed = (text || '').trim()
    if (!trimmed && !imageBase64) return
    // 命令不显示在聊天中
    if (!trimmed.startsWith('/')) {
      const content = imageBase64
        ? `[图片]${trimmed ? '\n' + trimmed : ''}`
        : trimmed
      messages.value.push({
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
        _image: imageBase64 || null,
      })
      totalMessages.value++
    }
    isStreaming.value = true
    pendingReply.value = ''
    error.value = null
    // 构造历史：过滤掉命令和系统消息
    const history = messages.value
      .filter(m => !m._isGreeting && !m.isProactive && !m.isSurprise && !m.content?.startsWith('/'))
      .slice(-35)
      .map(m => ({ role: m.role, content: m.content }))
    const payload = { message: trimmed || '[图片]', history }
    if (imageBase64) payload.image = imageBase64
    ws.value.send(JSON.stringify(payload))
  }

  function reroll() {
    if (!ws.value || ws.value.readyState !== 1 || isStreaming.value) return
    isStreaming.value = true
    pendingReply.value = ''
    ws.value.send(JSON.stringify({ message: '/reroll' }))
  }

  async function loadHistory() {
    isLoading.value = true
    try {
      const params = { limit: 200 }
      if (activeSessionId.value) params.session_id = activeSessionId.value
      const res = await api.get('/chat/history/', { params })
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
    } catch {
      error.value = '加载历史失败'
    } finally {
      isLoading.value = false
    }
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
      favoriteIds.value = new Set(favoriteIds.value)
    } catch {}
  }

  async function deleteMessage(msg) {
    if (!msg?.id) return
    try {
      await api.delete(`/chat/message/${msg.id}`)
      messages.value = messages.value.filter(m => m.id !== msg.id)
      totalMessages.value = messages.value.length
    } catch {}
  }

  async function loadSessions() {
    try {
      const res = await api.get('/chat/sessions/')
      sessions.value = res.data?.sessions || []
      const active = sessions.value.find(s => s.is_active)
      if (active) activeSessionId.value = active.id
    } catch {}
  }

  async function createSession(name) {
    try {
      const res = await api.post('/chat/sessions/', { name: name || '新会话' })
      await loadSessions()
      return res.data?.id
    } catch {}
  }

  async function switchSession(id) {
    try {
      await api.post(`/chat/sessions/${id}/switch`)
      activeSessionId.value = id
      await loadHistory()
    } catch {}
  }

  async function deleteSession(id) {
    try {
      await api.delete(`/chat/sessions/${id}`)
      await loadSessions()
    } catch {}
  }

  function switchCharacter(charId) {
    if (!ws.value || ws.value.readyState !== 1) return
    messages.value = []
    totalMessages.value = 0
    pendingReply.value = ''
    isStreaming.value = false
    error.value = null
    ws.value.send(JSON.stringify({ type: 'switch_character', character_id: charId }))
  }

  function disconnect() {
    if (_reconnectTimer) {
      clearTimeout(_reconnectTimer)
      _reconnectTimer = null
    }
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    wsReady.value = false
  }

  const lastAssistantMsg = computed(() => {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].role === 'assistant') return messages.value[i]
    }
    return null
  })

  return {
    messages, isStreaming, wsReady, totalMessages, pendingReply,
    favoriteIds, sessions, activeSessionId, isLoading, error, lastAssistantMsg,
    connectWebSocket, disconnect, switchCharacter,
    sendMessage, reroll, sendCommand,
    loadHistory, loadFavorites, toggleFavorite, deleteMessage,
    loadSessions, createSession, switchSession, deleteSession,
  }
})
