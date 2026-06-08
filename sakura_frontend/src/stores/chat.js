// stores/chat.js — 聊天状态（逐步从 App.vue 迁移）
import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import api, { createWebSocket } from '../api.js'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isStreaming = ref(false)
  const pendingReply = ref('')
  const wsReady = ref(false)
  const totalMessages = ref(0)
  const nextAfterId = ref(null)
  const loadingMore = ref(false)
  const historyReady = ref(false)
  const favoriteIds = ref(new Set())

  let ws = null
  let _onMessage = null

  function connect(onMessage) {
    _onMessage = onMessage
    if (ws && ws.readyState === WebSocket.OPEN) return
    try {
      ws = createWebSocket('/ws/chat')
    } catch (e) { scheduleReconnect(); return }
    ws.onopen = () => { wsReady.value = true }
    ws.onmessage = (event) => {
      if (_onMessage) _onMessage(event)
    }
    ws.onerror = () => { wsReady.value = false; try { ws.close() } catch(e) {} }
    ws.onclose = () => { wsReady.value = false; scheduleReconnect() }
  }

  let reconnectTimer = null
  let attempts = 0
  function scheduleReconnect() {
    if (reconnectTimer) return
    const delay = Math.min(30000, 1000 * Math.pow(2, attempts))
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      attempts++
      connect(_onMessage)
    }, delay)
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data))
    }
  }

  function disconnect() {
    if (ws) { ws.onclose = null; ws.close(); ws = null }
    wsReady.value = false
  }

  async function loadHistory() {
    try {
      const res = await api.get('/chat/history/', { params: { limit: 40 } })
      if (res.data && res.data.messages) {
        messages.value = res.data.messages
        totalMessages.value = messages.value.length
        nextAfterId.value = res.data.next_after_id || null
      }
    } catch (e) { console.error(e) }
    finally { historyReady.value = true }
  }

  async function loadMoreHistory() {
    if (!nextAfterId.value || loadingMore.value) return
    loadingMore.value = true
    try {
      const res = await api.get('/chat/history/', { params: { limit: 30, after_id: nextAfterId.value } })
      if (res.data && res.data.messages) {
        messages.value = [...res.data.messages, ...messages.value]
        totalMessages.value = messages.value.length
        nextAfterId.value = res.data.next_after_id || null
      }
    } catch (e) { console.error(e) }
    finally { loadingMore.value = false }
  }

  async function loadFavoriteIds() {
    try { const res = await api.get('/favorites'); favoriteIds.value = new Set((res.data || []).map(f => f.msg_id)) } catch(e) {}
  }

  function toggleFavorite(msg) {
    if (!msg?.id) return
    const ids = favoriteIds.value
    if (ids.has(msg.id)) {
      api.delete(`/favorites/${msg.id}`)
      ids.delete(msg.id)
    } else {
      api.post(`/favorites/${msg.id}`)
      ids.add(msg.id)
    }
  }

  return {
    messages, isStreaming, pendingReply, wsReady,
    totalMessages, nextAfterId, loadingMore, historyReady, favoriteIds,
    connect, send, disconnect, scheduleReconnect,
    loadHistory, loadMoreHistory, loadFavoriteIds, toggleFavorite,
  }
})
