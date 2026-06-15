// stores/chatStore.js — 聊天状态：WebSocket、消息流、打字机效果
import { defineStore } from 'pinia'
import { createWebSocket } from '../api'
import api from '../api'

export const useChatStore = defineStore('chat', {
  state: () => ({
    ws: null,
    wsReady: false,
    wsReconnectAttempts: 0,
    _reconnectTimer: null,
    messages: [],
    totalMessages: 0,
    reminderCount: 0,
    isStreaming: false,
    pendingReply: '',
    schedId: null,
    _currentReplyLen: 0,
    _sendingCooldown: false,
    nextAfterId: null,
    loadingMore: false,
    todayLearning: null,
    timelineDates: [],
    historyReady: false,
    _twQueue: [],
    _twActive: false,
    _twTimer: null,
    _streamTimeout: null,
    // 回调：App.vue 注入以操作 $refs
    _onGreeting: null,
    _onProactive: null,
    _onWeather: null,
    _onSurprise: null,
    _onDone: null,
    _scrollToBottom: null,
    _findNextSentence: null,
    _autoPlayTTS: null,
    sentenceMode: 'auto',
    _persistent_wndproc: null,
  }),

  actions: {
    /** 连接 WebSocket */
    connectWebSocket() {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) return
      if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
        try { this.ws.close() } catch (e) {}
      }
      try { this.ws = createWebSocket('/ws/chat') } catch (e) { this._scheduleReconnect(); return }

      this.ws.onopen = () => { this.wsReady = true; this.wsReconnectAttempts = 0 }
      this.ws.onmessage = (event) => {
        let data
        try { data = JSON.parse(event.data) } catch (e) { return }
        this._handleMessage(data)
      }
      this.ws.onerror = () => {
        this.wsReady = false
        this.stopTypewriter()
        try { this.ws.close() } catch (e) {}
      }
      this.ws.onclose = () => { this.wsReady = false; this.stopTypewriter(); this._scheduleReconnect() }
    },

    /** 处理 WebSocket 消息 */
    _handleMessage(data) {
      if (data.type === 'token') {
        if (this.pendingReply.length < 50000) this.pendingReply += data.content
        this._currentReplyLen = (this._currentReplyLen || 0) + data.content.length
        if (!this.schedId) this.schedulePop()
      } else if (data.type === 'done') {
        if (data._system) {
          this.pendingReply = ''
          this.isStreaming = false
        }
        this.stopTypewriter()
        if (this._onDone) this._onDone(data)
      } else if (data.type === 'greeting') {
        if (this._onGreeting) this._onGreeting(data)
      } else if (data.type === 'proactive') {
        if (this._onProactive) this._onProactive(data)
      } else if (data.type === 'weather') {
        if (this._onWeather) this._onWeather(data)
      } else if (data.type === 'reroll_start') {
        if (this.schedId) { clearTimeout(this.schedId); this.schedId = null }
        this.pendingReply = ''
        this.isStreaming = true
        this._currentReplyLen = 0
      } else if (data.type === 'surprise') {
        if (this._onSurprise) this._onSurprise(data)
      } else if (data.type === 'reminder') {
        // 由 App.vue 处理 toast
      } else if (data.type === 'reminder_count') {
        this.reminderCount = data.count || 0
      } else if (data.type === 'achievement') {
        // 由 App.vue 处理
      } else if (data.type === 'toast') {
        // 由 App.vue 处理
      } else if (data.type === 'dsml_tool_call') {
        this.pendingReply = ''
        this.isStreaming = false
        this.stopTypewriter()
      } else if (data.type === 'error') {
        this.messages.push({ role: 'assistant', content: '错误：' + data.content, timestamp: new Date().toISOString() })
        this.isStreaming = false
        this.stopTypewriter()
      }
    },

    /** 发送消息 */
    sendMessage(msg, history = []) {
      if (!msg) return
      if (!this.wsReady) return false
      if (this.isStreaming || this._sendingCooldown) return false
      this._sendingCooldown = true
      setTimeout(() => { this._sendingCooldown = false }, 500)
      this.isStreaming = true
      this.pendingReply = ''
      this._currentReplyLen = 0
      this.messages.push({ role: 'user', content: msg, timestamp: new Date().toISOString() })
      this.totalMessages++
      try {
        this.ws.send(JSON.stringify({
          message: msg,
          history: history.filter(m => !m._sentenceFrag && !m.isWeather && !m._isGreeting && !m.isProactive && !m.isSurprise).slice(0, -1).slice(-35).map(m => ({ role: m.role, content: m.content, timestamp: m.timestamp }))
        }))
      } catch (e) {
        this.messages.pop()
        this.totalMessages--
        this.isStreaming = false
        this.stopTypewriter()
        return false
      }
      if (this._scrollToBottom) this._scrollToBottom(true)
      clearTimeout(this._streamTimeout)
      this._streamTimeout = setTimeout(() => {
        if (this.isStreaming) {
          this.isStreaming = false
          this.stopTypewriter()
          if (this.pendingReply) {
            this.messages.push({ role: 'assistant', content: this.pendingReply + '\n(回复被中断，可重新发送消息)', timestamp: new Date().toISOString() })
            this.pendingReply = ''
          }
        }
      }, 60000)
      return true
    },

    /** 加载历史消息 */
    async loadHistory() {
      try {
        const res = await api.get('/chat/history/', { params: { limit: 40 } })
        if (res.data && res.data.messages) {
          this.messages = res.data.messages
          this.totalMessages = this.messages.length
          this.nextAfterId = res.data.next_after_id || null
          if (this._scrollToBottom) this._scrollToBottom(true)
        }
      } catch (e) { console.error(e) }
      finally { this.historyReady = true }
    },

    /** 加载更多历史 */
    async loadMoreHistory() {
      if (!this.nextAfterId || this.loadingMore) return
      this.loadingMore = true
      try {
        const res = await api.get('/chat/history/', { params: { limit: 30, after_id: this.nextAfterId } })
        if (res.data && res.data.messages) {
          const older = res.data.messages
          this.messages = [...older, ...this.messages]
          this.totalMessages = this.messages.length
          this.nextAfterId = res.data.next_after_id || null
        }
      } catch (e) { console.error(e) }
      finally { this.loadingMore = false }
    },

    /** 分句调度 */
    schedulePop() {
      if (this.schedId) return
      const pop = () => {
        this.schedId = null
        this.pendingReply = this.pendingReply.replace(/^[\s\n]+/, '')
        if (!this.pendingReply) return
        if (this.sentenceMode === 'raw') { this.pendingReply = ''; this.isStreaming = false; return }
        const result = this._findNextSentence ? this._findNextSentence(this.pendingReply) : null
        if (result) {
          const [sentence, rest] = result
          this.pendingReply = rest || ''
          if (this.sentenceMode === 'typewriter') { this._twPush(sentence) }
          else {
            const frag = { role: 'assistant', content: sentence, timestamp: new Date().toISOString(), _sentenceFrag: true }
            this.messages.push(frag)
            if (this._autoPlayTTS) this._autoPlayTTS(frag)
          }
          if (this._scrollToBottom) this._scrollToBottom()
          const jitter = 0.8 + Math.random() * 0.4
          const delay = Math.min(Math.max(300, 250 + sentence.length * 30), 2000) * jitter
          this.schedId = setTimeout(pop, delay | 0)
        } else if (!this.isStreaming) {
          const remain = this.pendingReply.trim()
          if (this.sentenceMode === 'typewriter' && remain) { this._twPush(remain) }
          else if (remain) {
            const frag = { role: 'assistant', content: remain, timestamp: new Date().toISOString() }
            this.messages.push(frag)
            if (this._autoPlayTTS) this._autoPlayTTS(frag)
          }
          this.pendingReply = ''
          if (this._scrollToBottom) this._scrollToBottom()
        } else {
          this.schedId = setTimeout(pop, 100)
        }
      }
      this.schedId = setTimeout(pop, 60)
    },

    /** 停止打字机效果 */
    stopTypewriter() {
      this.isStreaming = false
      clearTimeout(this._streamTimeout)
      if (this._twTimer) { clearTimeout(this._twTimer); this._twTimer = null }
      while (this._twQueue.length) {
        const s = this._twQueue.shift()
        const last = this.messages[this.messages.length - 1]
        if (!last || last.role !== 'assistant' || last._twDone) {
          this.messages.push({ role: 'assistant', content: s, timestamp: new Date().toISOString() })
        } else { last.content = last.content + s; last._twDone = true }
      }
      this._twActive = false
      if (this.schedId) { clearTimeout(this.schedId); this.schedId = null }
      if (this.pendingReply.trim()) this.schedulePop()
      const lastMsg = this.messages[this.messages.length - 1]
      if (lastMsg?.role === 'assistant' && this._autoPlayTTS) this._autoPlayTTS(lastMsg)
    },

    /** 打字机入队 */
    _twPush(sentence) {
      this._twQueue.push(sentence)
      if (!this._twActive) { this._twActive = true; this._twTick() }
    },

    /** 打字机逐字 */
    _twTick() {
      if (!this._twQueue.length) { this._twActive = false; return }
      let sentence = this._twQueue[0]
      const msgs = this.messages
      let last = msgs[msgs.length - 1]
      if (!last || last.role !== 'assistant' || last._twDone) {
        last = { role: 'assistant', content: '', timestamp: new Date().toISOString(), _twDone: false }
        msgs.push(last)
      }
      last.content += sentence[0] || ''
      sentence = sentence.slice(1)
      this._twQueue[0] = sentence
      if (sentence.length === 0) {
        this._twQueue.shift()
        last._twDone = true
        if (this._scrollToBottom) this._scrollToBottom()
      }
      this._twTimer = setTimeout(() => this._twTick(), 30 + Math.random() * 20)
    },

    /** 重连调度 */
    _scheduleReconnect() {
      if (this._reconnectTimer) return
      const delay = Math.min(30000, 1000 * Math.pow(2, this.wsReconnectAttempts))
      this._reconnectTimer = setTimeout(() => {
        this._reconnectTimer = null
        this.wsReconnectAttempts++
        this.connectWebSocket()
      }, delay)
    },
  },
})