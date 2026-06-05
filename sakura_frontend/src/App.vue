<template>
  <div class="app" :data-theme="currentTheme" :style="colorVariables">
    <LoginView v-if="needLogin" @login-success="onLoginSuccess" />
    <LockScreen v-else-if="showLockScreen" :on-unlock="unlock" />
    <OnboardingWizard v-if="showOnboarding" :aiName="aiNameLocal" @completed="onOnboardingCompleted" />
    <AchievementToast v-if="achievementPopup" :data="achievementPopup" />
    <div v-if="gameToast" class="game-toast">{{ gameToast }}</div>
    <FloatingCalendar v-if="activeView==='chat'" ref="floatingCalendar" />

    <div class="app-layout">
      <NavBar :active="activeView" :wsReady="wsReady" :aiName="aiNameLocal" @nav="onNav" @scroll-bottom="onScrollBottom" @reconnect="manualReconnect" />
      <div v-if="_reconnectMsg && _reconnectMsg.show" class="reconnect-banner">
        <span>{{ _reconnectMsg.text }}</span>
        <button class="reconnect-btn" @click="manualReconnect">立即重连</button>
      </div>

      <div class="main-area">
        <ChatView v-show="activeView==='chat'" ref="chatView"
          :ws="ws" :wsReady="wsReady" :messages="messages" :isStreaming="isStreaming"
          :pendingReply="pendingReply" :aiNameLocal="aiNameLocal" :userNameLocal="userNameLocal"
          :assistantAvatarUrl="assistantAvatarUrl" :userAvatarUrl="userAvatarUrl"
          :quickPhrases="quickPhrases" :favoriteIds="favoriteIds" :sentenceMode="sentenceMode"
          :quickReplies="quickReplies" :todayLearning="todayLearning"
          :timelineDates="timelineDates"
          :nextAfterId="nextAfterId" :loadingMore="loadingMore" :chatFontSize="chatFontSize"
          :ipCity="ipCity" :ipCityShort="ipCityShort" :totalMessages="totalMessages" :reminderCount="reminderCount" :kaomojis="kaomojis" :historyReady="historyReady"
          :voiceSettings="{ tts_enabled: allSettings.tts_enabled, tts_engine: allSettings.tts_engine, auto_play: allSettings.auto_play_voice, tts_clone_audio: allSettings.tts_clone_audio, tts_clone_mode: allSettings.tts_clone_mode }"
          @send="sendMessage" @toggle-favorite="toggleFavorite"
          @context-menu-action="onContextMenuAction"
          @load-more="loadMoreHistory" @delete-message="onDeleteMessage"
          @clear-today-learning="todayLearning = null"
          @feedback="onFeedback"
        />

        <ToolsView v-if="activeView==='tools'" :aiName="aiNameLocal" />

        <DiaryView v-if="activeView==='diary'" :aiName="aiNameLocal" />

        <GamesView v-if="activeView==='games'" @game-event="onGameEvent" @ai-help="onAiHelp" :aiName="aiNameLocal" />

        <StatsView v-if="activeView==='stats'" />

        <MemoryView v-if="activeView==='memory'" :aiName="aiNameLocal" />

        <SettingsView v-if="activeView==='settings'"
          :settings="allSettings" :themeLocal="themeLocal" :ipCity="ipCity"
          :relationship="relationship" :emotionTrend="emotionTrend"
          :totalMessages="totalMessages" :conversationDays="conversationDays"
          :assistantAvatarUrl="assistantAvatarUrl" :userAvatarUrl="userAvatarUrl"
          @config-changed="onSettingsChanged" @export-chat="exportChat"
          @close="activeView='chat'"
        />

        <HistoryView v-if="activeView==='history'"
          :favoriteIds="favoriteIds" :aiName="aiNameLocal" :userName="userNameLocal"
          @close="activeView='chat'" @toggle-favorite="toggleFavorite"
        />
      </div>
    </div>
  </div>

  <div v-if="confirmDialog.show" class="confirm-overlay" @click.self="confirmDialog.resolve(false);confirmDialog.show=false">
    <div class="confirm-box"><div class="confirm-msg">{{ confirmDialog.msg }}</div>
      <div class="confirm-btns"><button class="btn" @click="confirmDialog.resolve(true);confirmDialog.show=false">确定</button><button class="btn-s" @click="confirmDialog.resolve(false);confirmDialog.show=false">取消</button></div>
    </div>
  </div>
</template>

<script>
import api, { createWebSocket } from './api.js'
import LoginView from './components/LoginView.vue'
import NavBar from './components/NavBar.vue'
import ChatView from './components/ChatView.vue'
import ToolsView from './components/ToolsView.vue'
import StatsView from './components/StatsView.vue'
import GamesView from './components/GamesView.vue'
import MemoryView from './components/MemoryView.vue'
import SettingsView from './components/SettingsView.vue'
import LockScreen from './components/LockScreen.vue'
import OnboardingWizard from './components/OnboardingWizard.vue'
import AchievementToast from './components/AchievementToast.vue'
import HistoryView from './components/HistoryView.vue'
import DiaryView from './components/DiaryView.vue'
import FloatingCalendar from './components/FloatingCalendar.vue'

export default {
  components: { NavBar, ChatView, ToolsView, StatsView, GamesView, MemoryView, SettingsView, LockScreen, OnboardingWizard, AchievementToast, HistoryView, DiaryView, FloatingCalendar, LoginView },
  provide() { return { showConfirm: this.showConfirm } },
  data() {
    return {
      activeView: 'chat', currentTheme: 'dark', themeLocal: 'dark',
      ws: null, wsReady: false, wsReconnectAttempts: 0, _reconnectTimer: null, _reconnectMsg: null,
      messages: [], totalMessages: 0, conversationDays: 0, reminderCount: 0,
      isStreaming: false, pendingReply: '', schedId: null, _currentReplyLen: 0, _sendingCooldown: false,
      nextAfterId: null, loadingMore: false,
      showEmojiPicker: false,
      allSettings: {},
      aiNameLocal: '佐仓', userNameLocal: '', toneLocal: '冷静',
      assistantAvatarUrl: '', userAvatarUrl: '',
      relationship: {}, emotionTrend: [], ipCity: '', ipCityShort: '',
      showContextMenu: false, ctxMenuX: 0, ctxMenuY: 0, ctxTargetMsg: null,
      showOnboarding: false, showLockScreen: false, needLogin: false,
      pinEnabled: false, pinCode: '', pinInput: '', pinError: '',
      favoriteIds: new Set(), quickPhrases: [],
      achievementPopup: null, gameToast: null, _toastTimer: null, _systemStreaming: false, bgOpacity: 1, bgBlur: 0, bgMode: 'cover', chatBgImage: '', chatFontSize: 14,
      confirmDialog: { show: false, msg: '', resolve: null },
      todayLearning: null, timelineDates: [], historyReady: false,
      quickReplies: ['展开说说', '换个角度', '好的', '继续'], sentenceMode: 'auto',
      _twQueue: [], _twActive: false, _twTimer: null,
      _streamTimeout: null, _locationTimer: null, _mediaDark: null,
    }
  },
  computed: {
    colorVariables() {
      let bg = 'none'
      if (this.chatBgImage && /^(https?:\/\/|\/)[^\s'"()]+\.(jpg|jpeg|png|webp|gif)(\?[^\s'"()]*)?$/i.test(this.chatBgImage)) {
        bg = `url("${this.chatBgImage}")`
      }
      return { '--chat-bg-img': bg, '--bg-opacity': this.bgOpacity, '--bg-blur': this.bgBlur + 'px', '--bg-mode': this.bgMode }
    },
    kaomojis() { return ['(・ω・)','(´∀｀)','(╯°□°)╯','( ；∀；)','(￣▽￣)','(⌒▽⌒)','（＾ω＾）','(・∀・)','(｀・ω・´)','(＞＜)','(T_T)','(^_^;)','( ´ ▽ ` )','(・へ・)','(≧∇≦)','(-_-;)','(￣ε￣)','(・_・;)','(゜∀゜)','(；一_一)','( ´ー｀)','(´・ω・｀)','(Θ_Θ)','(。-ω-)zzz','ヽ(・∀・)ノ'] },
  },
  async mounted() {
    // 云端模式：检查是否需要登录
    const cfg = window.__SAKURA_CONFIG__ || {}
    const isCloudMode = !!cfg.backendHost
    if (isCloudMode) {
      const savedToken = localStorage.getItem('sakura_api_token')
      if (!savedToken) {
        this.needLogin = true
        return
      }
    }

    await this.loadAllSettings()
    // PIN 重置恢复
    try {
      if (localStorage.getItem('_reset_pin') === '1') {
        localStorage.removeItem('_reset_pin')
        await api.post('/settings/', { key: 'pin_code', value: '' })
        await api.post('/settings/', { key: 'pin_enabled', value: false })
        this.pinEnabled = false; this.pinCode = ''
      }
    } catch (e) {}
    this.checkOnboarding()
    this.loadAvatars()
    this.loadFavoriteIds()
    this.loadHistory()
    this.loadTodayLearning()
    this.loadTimelineDates()
    this.maybeShowLockScreen()
    this.connectWebSocket()
    this.loadRelationship()
    this.loadEmotionTrend()
    // 定位：立即获取IP定位，之后每5分钟更新
    this.loadIpLocation()
    this._locationTimer = setInterval(() => { if (!this._unmounted && document.visibilityState === 'visible') this.loadIpLocation() }, 300000)
    if (Notification.permission === 'default') Notification.requestPermission()
    this._mediaDark = window.matchMedia('(prefers-color-scheme: dark)')
    this._mediaDark.addEventListener('change', this._onSystemThemeChange)
    document.addEventListener('keydown', this._keydownHandler)
    this._wheelHandler = (e) => { if (e.ctrlKey) { e.preventDefault(); this.chatFontSize = Math.min(20, Math.max(10, this.chatFontSize + (e.deltaY > 0 ? 1 : -1))) } }
    document.addEventListener('wheel', this._wheelHandler, { passive: false })
  },
  beforeUnmount() {
    this._unmounted = true
    if (this.ws) { this.ws.onclose = null; this.ws.onerror = null; this.ws.close() }
    clearTimeout(this._locationTimer); clearInterval(this._locationTimer)
    clearTimeout(this._reconnectTimer)
    clearTimeout(this._twTimer)
    clearTimeout(this._streamTimeout)
    clearTimeout(this._achieveTimer)
    clearTimeout(this.schedId)
    document.removeEventListener('keydown', this._keydownHandler)
    if (this._wheelHandler) document.removeEventListener('wheel', this._wheelHandler)
    if (this._mediaDark) this._mediaDark.removeEventListener('change', this._onSystemThemeChange)
  },
  methods: {
    // ── Login ──
    async onLoginSuccess(token) {
      this.needLogin = false
      await this.loadAllSettings()
      this.checkOnboarding()
      this.loadAvatars()
      this.loadFavoriteIds()
      this.loadHistory()
      this.loadTodayLearning()
      this.loadTimelineDates()
      this.loadRelationship()
      this.loadEmotionTrend()
      this.connectWebSocket()
      this.loadIpLocation()
    },
    // ── Navigation ──
    onNav(view) { this.activeView = view; if (this.$refs.chatView) this.$refs.chatView.showCtx = false },
    onScrollBottom() { this.$refs.chatView?.forceScrollToBottom() },
    onDeleteMessage(id) { this.messages = this.messages.filter(m => m.id !== id); this.totalMessages = this.messages.length },
    onFeedback({ msgId, score }) {
      // 发送反馈到后端
      if (this.ws && this.wsReady) {
        this.ws.send(JSON.stringify({ type: 'feedback', msg_id: msgId, score }))
      }
    },
    showConfirm(msg) { return new Promise(resolve => { this.confirmDialog = { show: true, msg, resolve } }) },
    // ── Theme ──
    _resolveTheme(t) { const valid = ['dark','light','sakura','vesper']; return valid.includes(t) ? t : 'dark' },
    _onSystemThemeChange(e) {},
    // ── Settings ──
    async loadAllSettings() {
      try {
        const res = await api.get('/settings/')
        const s = res.data
        this.allSettings = s
        this.themeLocal = s.theme || 'dark'; this.currentTheme = this._resolveTheme(this.themeLocal)
        document.documentElement.setAttribute('data-theme', this.currentTheme)
        this.aiNameLocal = s.ai_name || '佐仓'; this.userNameLocal = s.user_name || ''
        if (s.precise_city) { this.ipCity = s.precise_city; const parts = s.precise_city.split('·'); this.ipCityShort = parts[parts.length - 1] || s.precise_city }
        if (s.chat_bg_image) this.chatBgImage = s.chat_bg_image
        if (s.bg_opacity !== undefined) this.bgOpacity = Number(s.bg_opacity)
        if (s.bg_blur !== undefined) this.bgBlur = Number(s.bg_blur)
        if (s.bg_mode) this.bgMode = s.bg_mode
        if (s.quick_phrases) { try { this.quickPhrases = JSON.parse(s.quick_phrases) } catch (e) { this.quickPhrases = [] } }
        if (s.pin_enabled !== undefined) this.pinEnabled = s.pin_enabled === 'true' || s.pin_enabled === true
        if (s.pin_code) this.pinCode = s.pin_code
        if (s.sentence_mode) this.sentenceMode = s.sentence_mode
        if (s.chat_font_size) this.chatFontSize = Number(s.chat_font_size)
      } catch (e) { console.error(e) }
    },
    onSettingsChanged(key, value) {
      this.allSettings[key] = value
      if (key === 'theme') { this.currentTheme = this._resolveTheme(value); this.themeLocal = value; document.documentElement.setAttribute('data-theme', this.currentTheme); const meta = document.getElementById('theme-color-meta'); const tc = { dark: '#0f1119', light: '#f5f0e8', sakura: '#1c141a', vesper: '#13101c' }; if (meta) meta.content = tc[this.currentTheme] || '#0f1119' }
      else if (key === 'ai_name') this.aiNameLocal = value
      else if (key === 'user_name') this.userNameLocal = value
      else if (key === 'quick_phrases') { try { this.quickPhrases = JSON.parse(value) } catch (e) { this.quickPhrases = value || [] } }
      else if (key === 'bg_style') { if (value.opacity !== undefined) this.bgOpacity = value.opacity; if (value.blur !== undefined) this.bgBlur = value.blur; if (value.mode) this.bgMode = value.mode }
      else if (key === 'chat_bg_image') this.chatBgImage = value
      else if (key === 'sentence_mode') this.sentenceMode = value
      else if (key === 'precise_city') { this.ipCity = value; const parts = value.split('·'); this.ipCityShort = parts[parts.length - 1] || value }
      else if (key === 'avatar_updated') { this.loadAvatars() }
    },
    // ── WebSocket ──
    connectWebSocket() {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) return
      if (this.ws && this.ws.readyState === WebSocket.CONNECTING) { try { this.ws.close() } catch (e) {} }
      try { this.ws = createWebSocket('/ws/chat') } catch (e) { this.scheduleReconnect(); return }
      this.ws.onopen = () => { this.wsReady = true; this.wsReconnectAttempts = 0 }
      this.ws.onmessage = (event) => {
        let data; try { data = JSON.parse(event.data) } catch (e) { return }
        if (data.type === 'token') { if (this._systemStreaming) return; if (this.pendingReply.length < 50000) { this.pendingReply += data.content }; this._currentReplyLen = (this._currentReplyLen || 0) + data.content.length; if (!this.schedId) this.schedulePop() }
        else if (data.type === 'done') { if (data._system) { this._systemStreaming = false; this.pendingReply = ''; this.isStreaming = false; this.stopTypewriter() } else { this.stopTypewriter() } this.$refs.floatingCalendar?.loadSchedules?.() }
        else if (data.type === 'greeting') { const last = this.messages[this.messages.length - 1]; if (!last || (last.role === 'assistant' && !last.isProactive && !last._isGreeting) || last.role === 'user') { this.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString(), _isGreeting: true }); this.totalMessages++; this.$nextTick(() => this.$refs.chatView?.scrollToBottom()) } }
        else if (data.type === 'proactive') { const last2 = this.messages.slice(-2); const hasProactive = last2.some(m => m.role === 'assistant' && m.isProactive); if (!hasProactive) { this.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString(), isProactive: true }); this.totalMessages++; this.$nextTick(() => this.$refs.chatView?.scrollToBottom()) } }
        else if (data.type === 'weather') { this.messages.push({ role: 'assistant', content: '__WEATHER_CARD__', weatherData: data.data, timestamp: new Date().toISOString(), isWeather: true }); this.totalMessages++; this.$nextTick(() => this.$refs.chatView?.scrollToBottom()) }
        else if (data.type === 'reroll_start') { if (this.schedId) { clearTimeout(this.schedId); this.schedId = null }; this.pendingReply = ''; this.isStreaming = true; this._currentReplyLen = 0 }
        else if (data.type === 'surprise') { this.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString(), isSurprise: true }); this.totalMessages++; this.$nextTick(() => this.$refs.chatView?.scrollToBottom()) }
        else if (data.type === 'reminder') { const rText = data.data?.content || data.data?.title || ''; this.gameToast = '⏰ 提醒：' + rText; clearTimeout(this._toastTimer); this._toastTimer = setTimeout(() => { this.gameToast = null }, 8000); this.reminderCount = Math.max(0, (this.reminderCount || 0)) }
        else if (data.type === 'reminder_count') { this.reminderCount = data.count || 0 }
        else if (data.type === 'achievement') { this.achievementPopup = data.data; clearTimeout(this._achieveTimer); this._achieveTimer = setTimeout(() => { this.achievementPopup = null }, 5000) }
        else if (data.type === 'toast') { this.gameToast = data.content; clearTimeout(this._toastTimer); const dur = Math.min(10000, Math.max(3000, (data.content || '').length * 80)); this._toastTimer = setTimeout(() => { this.gameToast = null }, dur) }
        else if (data.type === 'dsml_tool_call') { this.pendingReply = ''; this.isStreaming = false; this.stopTypewriter(); const last = this.messages[this.messages.length - 1]; if (last && last.role === 'assistant' && last.content && last.content.includes('DSML')) { this.messages.pop(); this.totalMessages-- } }
        else if (data.type === 'error') { this.messages.push({ role: 'assistant', content: '错误：' + data.content, timestamp: new Date().toISOString() }); this.isStreaming = false; this.stopTypewriter() }
      }
      this.ws.onerror = () => { this.wsReady = false; this.stopTypewriter(); try { this.ws.close() } catch (e) {} this.showDisconnectToast() }
      this.ws.onclose = () => { this.wsReady = false; this.stopTypewriter(); this.scheduleReconnect() }
    },
    showDisconnectToast() { this._reconnectMsg = { show: true, text: '连接已断开，正在重连...' }; setTimeout(() => { if (this._reconnectMsg) this._reconnectMsg.show = false }, 8000) },
    manualReconnect() { this.wsReconnectAttempts = 0; clearTimeout(this._reconnectTimer); this._reconnectTimer = null; this.connectWebSocket() },
    scheduleReconnect() { if (this._reconnectTimer || this._unmounted) return; const delay = Math.min(30000, 1000 * Math.pow(2, this.wsReconnectAttempts)); this._reconnectTimer = setTimeout(() => { this._reconnectTimer = null; if (!this._unmounted) { this.wsReconnectAttempts++; this.showDisconnectToast(); this.connectWebSocket() } }, delay) },
    sendMessage(msg) { if (!msg) return; if (!this.wsReady) { this.showDisconnectToast(); return } if (this.isStreaming || this._sendingCooldown) return; this._sendingCooldown = true; setTimeout(() => { this._sendingCooldown = false }, 500); this.isStreaming = true; this.pendingReply = ''; this._currentReplyLen = 0; this.messages.push({ role: 'user', content: msg, timestamp: new Date().toISOString() }); this.totalMessages++; try { this.ws.send(JSON.stringify({ message: msg, history: this.messages.filter(m => !m._sentenceFrag && !m.isWeather && !m._isGreeting && !m.isProactive && !m.isSurprise).slice(0, -1).slice(-35).map(m => ({ role: m.role, content: m.content, timestamp: m.timestamp })) })) } catch (e) { this.messages.pop(); this.totalMessages--; this.isStreaming = false; this.stopTypewriter(); return } this.$nextTick(() => this.$refs.chatView?.scrollToBottom(true)); clearTimeout(this._streamTimeout); this._streamTimeout = setTimeout(() => { if (this.isStreaming) { this.isStreaming = false; this.stopTypewriter(); if (this.pendingReply) { this.messages.push({ role: 'assistant', content: this.pendingReply + '\n(回复被中断，可重新发送消息)', timestamp: new Date().toISOString() }); this.pendingReply = '' } } }, 60000) },
    // ── Chat helpers ──
    schedulePop() { if (this.schedId) return; const pop = () => { this.schedId = null; this.pendingReply = this.pendingReply.replace(/^[\s\n]+/, ''); if (!this.pendingReply) return; if (this.sentenceMode === 'raw') { this.pendingReply = ''; this.isStreaming = false; return } const result = this.$refs.chatView?.findNextSentence?.(this.pendingReply); if (result) { const [sentence, rest] = result; this.pendingReply = rest || ''; if (this.sentenceMode === 'typewriter') { this._twPush(sentence) } else { const frag = { role: 'assistant', content: sentence, timestamp: new Date().toISOString(), _sentenceFrag: true }; this.messages.push(frag); this.$refs.chatView?.autoPlayTTS(frag) } this.$nextTick(() => this.$refs.chatView?.scrollToBottom()); const jitter = 0.8 + Math.random() * 0.4; const delay = Math.min(Math.max(300, 250 + sentence.length * 30), 2000) * jitter; this.schedId = setTimeout(pop, delay | 0) } else if (!this.isStreaming) { const remain = this.pendingReply.trim(); if (this.sentenceMode === 'typewriter' && remain) { this._twPush(remain) } else if (remain) { const frag = { role: 'assistant', content: remain, timestamp: new Date().toISOString() }; this.messages.push(frag); this.$refs.chatView?.autoPlayTTS(frag) } this.pendingReply = ''; this.$nextTick(() => this.$refs.chatView?.scrollToBottom()) } else { this.schedId = setTimeout(pop, 100) } }; this.schedId = setTimeout(pop, 60) },
    stopTypewriter() { this.isStreaming = false; clearTimeout(this._streamTimeout); if (this._twTimer) { clearTimeout(this._twTimer); this._twTimer = null }; while (this._twQueue.length) { const s = this._twQueue.shift(); const last = this.messages[this.messages.length - 1]; if (!last || last.role !== 'assistant' || last._twDone) { this.messages.push({ role: 'assistant', content: s, timestamp: new Date().toISOString() }) } else { last.content = last.content + s; last._twDone = true } } this._twActive = false; if (this.schedId) { clearTimeout(this.schedId); this.schedId = null } if (this.pendingReply.trim()) { this.schedulePop() } const lastMsg = this.messages[this.messages.length - 1]; if (lastMsg?.role === 'assistant') { this.$refs.chatView?.autoPlayTTS(lastMsg) } },
    _twPush(sentence) { this._twQueue.push(sentence); if (!this._twActive) { this._twActive = true; this._twTick() } },
    _twTick() {
      if (!this._twQueue.length) { this._twActive = false; return }
      let sentence = this._twQueue[0]
      const msgs = this.messages; let last = msgs[msgs.length - 1]
      if (!last || last.role !== 'assistant' || last._twDone) {
        last = { role: 'assistant', content: '', timestamp: new Date().toISOString(), _twDone: false }
        msgs.push(last)
      }
      last.content += sentence[0] || ''
      sentence = sentence.slice(1); this._twQueue[0] = sentence
      if (sentence.length === 0) { this._twQueue.shift(); last._twDone = true; this.$nextTick(() => this.$refs.chatView?.scrollToBottom()) }
      this._twTimer = setTimeout(() => this._twTick(), 30 + Math.random() * 20)
    },
    async loadHistory() { try { const res = await api.get('/chat/history/', { params: { limit: 40 } }); if (res.data && res.data.messages) { this.messages = res.data.messages; this.totalMessages = this.messages.length; this.nextAfterId = res.data.next_after_id || null; this.$nextTick(() => this.$refs.chatView?.scrollToBottom(true)) } } catch (e) { console.error(e) } finally { this.historyReady = true } },
    async loadMoreHistory() { if (!this.nextAfterId || this.loadingMore) return; this.loadingMore = true; try { const el = this.$refs.chatView?.$el?.querySelector('.msg-list'); const oldScrollHeight = el?.scrollHeight || 0; const oldScrollTop = el?.scrollTop || 0; const res = await api.get('/chat/history/', { params: { limit: 30, after_id: this.nextAfterId } }); if (res.data && res.data.messages) { const older = res.data.messages; this.messages = [...older, ...this.messages]; this.totalMessages = this.messages.length; this.nextAfterId = res.data.next_after_id || null; this.$nextTick(() => { if (el) el.scrollTop = oldScrollTop + (el.scrollHeight - oldScrollHeight) }) } } catch (e) { console.error(e) } finally { this.loadingMore = false } },
    // ── Favorites ──
    isMsgFavorite(msg) { return msg && msg.id && this.favoriteIds.has(msg.id) },
    async toggleFavorite(msg) { if (!msg?.id) return; try { if (this.favoriteIds.has(msg.id)) { await api.delete(`/favorites/${msg.id}`); this.favoriteIds.delete(msg.id) } else { await api.post(`/favorites/${msg.id}`); this.favoriteIds.add(msg.id) } } catch (e) {} },
    async loadFavoriteIds() { try { const res = await api.get('/favorites'); this.favoriteIds = new Set((res.data || []).map(f => f.msg_id)) } catch (e) {} },
    onContextMenuAction(action, msg) {
      if (action === 'toggle-favorite') this.toggleFavorite(msg)
      else if (action === 'reroll-from' && msg?.id && this.wsReady) {
        const idx = this.messages.findIndex(m => m.id === msg.id)
        if (idx !== -1) { this.messages = this.messages.slice(0, idx); this.totalMessages = this.messages.length }
        this.isStreaming = true; this.pendingReply = ''; this._currentReplyLen = 0
        this.ws.send(JSON.stringify({ message: `/reroll_from:${msg.id}`, history: this.messages.filter(m => !m._sentenceFrag).slice(-35).map(m => ({ role: m.role, content: m.content })) }))
      }
    },
    // ── Other ──
    async loadTodayLearning() { try { const res = await api.get('/memory/today-learning'); if (res.data?.has_new) this.todayLearning = res.data } catch (e) {} },
    async loadTimelineDates() { try { const res = await api.get('/chat/history/dates'); const months = res.data?.months || []; this.timelineDates = months.flatMap(m => (m.dates || []).map(d => d.date)) } catch (e) {} },
    maybeShowLockScreen() { if (this.pinEnabled && this.pinCode) { this.showLockScreen = true; this.pinInput = ''; this.pinError = '' } },
    unlock(pin) { if (pin === this.pinCode) { this.showLockScreen = false } else { return false } return true },
    async checkOnboarding() { try { const res = await api.get('/settings/onboarding-status'); if (res.data?.needs_onboarding) this.showOnboarding = true } catch (e) {} },
    onOnboardingCompleted() { this.showOnboarding = false; this.loadAllSettings(); this.connectWebSocket() },
    async loadAvatars() { try { const res = await api.get('/avatar/assistant'); if (res.data?.url) this.assistantAvatarUrl = res.data.url } catch (e) {}; try { const res = await api.get('/avatar/user'); if (res.data?.url) this.userAvatarUrl = res.data.url } catch (e) {} },
    async loadIpLocation() { try { const res = await api.get('/location/ip'); if (res.data?.city) { if (!this.allSettings.precise_city) { this.ipCity = res.data.city; this.ipCityShort = res.data.city } api.post('/settings/', { key: 'manual_city', value: res.data.city }).catch(() => {}) } } catch (e) {} },
    sendSystemMessage(msg) {
      if (!this.wsReady || this.isStreaming) return
      this._systemStreaming = true; this.isStreaming = true; this.pendingReply = ''; this._currentReplyLen = 0
      this.ws.send(JSON.stringify({ message: msg, history: this.messages.filter(m => !m._sentenceFrag && !m._gameEvent && !m._isGreeting && !m.isProactive).slice(-3).map(m => ({ role: m.role, content: m.content })), _system: true }))
      this._streamTimeout = setTimeout(() => { if (this.isStreaming) { this.isStreaming = false; this._systemStreaming = false; this.stopTypewriter() } }, 15000)
    },
    onAiHelp(evt) {
      if (!evt) return
      const msg = this.aiNameLocal + '救我！我正玩' + evt.game + '呢，快帮帮我！'
      this.sendSystemMessage(msg)
    },
    onGameEvent(evt) {
      if (!evt || this.isStreaming) return
      const map = { high_score: '刷新了最高分', game_won: '通关了', game_lost: '输了', reached_2048: '合出了2048', game_over: '游戏结束' }
      const act = map[evt.type] || evt.type
      let msg = evt.game + '：' + act + '！'
      if (evt.score) msg += '得分' + evt.score
      if (evt.difficulty) msg += '，' + ({easy:'简单',medium:'中等',hard:'困难'}[evt.difficulty]||evt.difficulty)
      this.sendSystemMessage(msg)
    },
    async loadRelationship() { try { const res = await api.get('/relationship/'); this.relationship = res.data } catch (e) {} },
    async loadEmotionTrend() { try { const res = await api.get('/emotion/trend?days=14'); this.emotionTrend = res.data || [] } catch (e) {} },
    async exportChat(fmt) { const format = fmt || 'txt'; try { const res = await api.get(`/export/chat?format=${format}`); const blob = new Blob([res.data.content], { type: format === 'md' ? 'text/markdown' : 'text/plain' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = res.data.filename; a.click(); URL.revokeObjectURL(url) } catch (e) { alert('导出失败') } },
    _keydownHandler(e) {
      const tag = document.activeElement?.tagName; const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
      if (e.key === 'Escape') { if (this.$refs.chatView) this.$refs.chatView.showCtx = false; this.showEmojiPicker = false }
      else if ((e.ctrlKey || e.metaKey) && !isInput) {
        if (e.key === '1') { e.preventDefault(); this.activeView = 'chat' }
        else if (e.key === '2') { e.preventDefault(); this.activeView = 'tools' }
        else if (e.key === '3') { e.preventDefault(); this.activeView = 'stats' }
        else if (e.key === '4') { e.preventDefault(); this.activeView = 'memory' }
        else if (e.key === '5') { e.preventDefault(); this.activeView = 'settings' }
		else if (e.key === '6') { e.preventDefault(); this.activeView = 'games' }
        else if (e.key === 'n' || e.key === 'N') { e.preventDefault(); this.confirmDialog = { show: true, msg: '⚠️ 确定要清空所有聊天记录吗？此操作不可恢复。', resolve: (ok) => { this.confirmDialog.show = false; if (ok) { api.delete('/chat/manage/all').then(() => { this.messages = []; this.totalMessages = 0; this.nextAfterId = null }).catch(() => {}) } } } }
      }
    },
  }
}
</script>

<style>
:root { color-scheme: dark; --p: #6a9fd8; --bg: #0f1119; --sb: #161927; --cb: #0f1119; --ub: #1d3557; --ab: #181e2b; --border: #252d3a; --tc: #e2e8f0; --tc2: #7b8ca0; --accent: #4a7fb5; }
:root[data-theme="light"] { --p: #c9717a; --bg: #f5f0e8; --sb: #ebe3d8; --cb: #f5f0e8; --ub: #c9717a; --ab: #faf7f0; --border: #d8cfc4; --tc: #3d3228; --tc2: #8c7b6e; --accent: #d4a090; }
:root[data-theme="vesper"] { --p: #9b8fb8; --bg: #13101c; --sb: #1c1828; --cb: #13101c; --ub: #2d2548; --ab: #1e1832; --border: #2a2240; --tc: #e0d8f0; --tc2: #8a7ab0; --accent: #c4b8e8; }
:root[data-theme="sakura"] { --p: #e8929b; --bg: #1c141a; --sb: #261c22; --cb: #1c141a; --ub: #3d2a35; --ab: #241c22; --border: #3d2a35; --tc: #f0d8e0; --tc2: #b8959e; --accent: #8fbc8f; }
* { margin: 0; padding: 0; box-sizing: border-box; scrollbar-width: none; }
*::-webkit-scrollbar { display: none; }
input, select, textarea, button { font-family: inherit; }
select { appearance: none; -webkit-appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23888' d='M6 8L1 3h10z'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 10px center; padding-right: 28px; }
.del-btn { background: none; border: none; color: var(--tc2); cursor: pointer; font-size: 11px; padding: 2px 4px; opacity: .4; transition: opacity .15s,color .15s; }
.del-btn:hover { opacity: 1; color: #e74c3c; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--tc); overflow: hidden; height: 100dvh; }
.app { display: flex; height: 100dvh; width: 100vw; }
.app-layout { display: flex; flex: 1; height: 100dvh; overflow: hidden; }
.main-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
.reconnect-banner { display: flex; align-items: center; justify-content: space-between; padding: 6px 16px; background: rgba(248,81,73,.15); border-bottom: 1px solid rgba(248,81,73,.3); color: var(--tc); font-size: 13px; z-index: 100; }
.reconnect-btn { padding: 4px 12px; background: var(--p, #5390d4); color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; }
.reconnect-btn:hover { filter: brightness(1.1); }

/* 移动端：底部导航栏适配 */
@media (max-width: 768px) {
  .app-layout { flex-direction: column; }
  .main-area { padding-bottom: 64px; /* 底部导航栏高度 + 安全区 */ }
  .confirm-box { min-width: 0; max-width: 90vw; margin: 0 16px; }
  .game-toast { right: 16px; left: 16px; max-width: none; }
}
/* ═══ 夕语星光 ═══ */
[data-theme="vesper"] .main-area::before { content: ''; position: absolute; inset: 0; z-index: 0; pointer-events: none; background-image: radial-gradient(1px 1px at 3% 10%, rgba(196,184,232,.7), transparent), radial-gradient(1.5px 1.5px at 7% 55%, rgba(155,143,184,.5), transparent), radial-gradient(1px 1px at 11% 28%, rgba(196,184,232,.4), transparent), radial-gradient(2px 2px at 15% 78%, rgba(155,143,184,.6), transparent), radial-gradient(1px 1px at 22% 8%, rgba(196,184,232,.5), transparent), radial-gradient(1.5px 1.5px at 28% 45%, rgba(155,143,184,.4), transparent), radial-gradient(1px 1px at 33% 68%, rgba(196,184,232,.6), transparent), radial-gradient(1px 1px at 38% 15%, rgba(155,143,184,.3), transparent), radial-gradient(2px 2px at 42% 52%, rgba(196,184,232,.5), transparent), radial-gradient(1px 1px at 48% 80%, rgba(155,143,184,.4), transparent), radial-gradient(1.5px 1.5px at 53% 22%, rgba(196,184,232,.6), transparent), radial-gradient(1px 1px at 58% 62%, rgba(155,143,184,.4), transparent), radial-gradient(1px 1px at 63% 38%, rgba(196,184,232,.3), transparent), radial-gradient(2px 2px at 68% 72%, rgba(155,143,184,.5), transparent), radial-gradient(1px 1px at 73% 5%, rgba(196,184,232,.5), transparent), radial-gradient(1.5px 1.5px at 78% 48%, rgba(155,143,184,.4), transparent), radial-gradient(1px 1px at 83% 85%, rgba(196,184,232,.6), transparent), radial-gradient(1px 1px at 88% 18%, rgba(155,143,184,.3), transparent), radial-gradient(2px 2px at 93% 55%, rgba(196,184,232,.5), transparent), radial-gradient(1px 1px at 97% 75%, rgba(155,143,184,.4), transparent); animation: vesper-twinkle 5s ease-in-out infinite alternate; }
@keyframes vesper-twinkle { 0% { opacity: .4; } 50% { opacity: .7; } 100% { opacity: .5; } }
/* ═══ 樱花花瓣 ═══ */
[data-theme="sakura"] .main-area::before { content: ''; position: absolute; inset: 0; z-index: 0; pointer-events: none; background-image: radial-gradient(2px 3px at 5% 15%, rgba(232,146,155,.45), transparent), radial-gradient(2px 2px at 12% 45%, rgba(143,188,143,.25), transparent), radial-gradient(3px 2px at 20% 8%, rgba(232,146,155,.4), transparent), radial-gradient(2px 3px at 25% 65%, rgba(232,146,155,.35), transparent), radial-gradient(2px 2px at 32% 32%, rgba(143,188,143,.2), transparent), radial-gradient(3px 2px at 38% 78%, rgba(232,146,155,.45), transparent), radial-gradient(2px 3px at 45% 12%, rgba(143,188,143,.25), transparent), radial-gradient(2px 2px at 52% 52%, rgba(232,146,155,.4), transparent), radial-gradient(3px 2px at 58% 85%, rgba(232,146,155,.35), transparent), radial-gradient(2px 3px at 65% 22%, rgba(143,188,143,.25), transparent), radial-gradient(2px 2px at 72% 58%, rgba(232,146,155,.45), transparent), radial-gradient(3px 2px at 78% 5%, rgba(232,146,155,.4), transparent), radial-gradient(2px 3px at 85% 42%, rgba(143,188,143,.2), transparent), radial-gradient(2px 2px at 90% 72%, rgba(232,146,155,.35), transparent), radial-gradient(3px 2px at 95% 25%, rgba(232,146,155,.45), transparent), radial-gradient(2px 3px at 8% 92%, rgba(143,188,143,.25), transparent), radial-gradient(2px 2px at 42% 95%, rgba(232,146,155,.35), transparent), radial-gradient(3px 2px at 68% 92%, rgba(143,188,143,.2), transparent); animation: sakura-float 8s ease-in-out infinite alternate; }
@keyframes sakura-float { 0% { opacity: .35; transform: translateY(0); } 100% { opacity: .55; transform: translateY(-4px); } }
.confirm-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 3000; display: flex; align-items: center; justify-content: center; }
.confirm-box { background: var(--sb); border: 1px solid var(--border); border-radius: 12px; padding: 24px; min-width: 300px; max-width: 420px; box-shadow: 0 8px 32px rgba(0,0,0,.4); }
.confirm-msg { font-size: 14px; color: var(--tc); margin-bottom: 16px; line-height: 1.6; }
.confirm-btns { display: flex; gap: 8px; justify-content: flex-end; }
.game-toast { position: fixed; top: 16px; right: 20px; max-width: 260px; padding: 10px 14px; background: var(--sb); border: 1px solid var(--p); border-radius: 10px; color: var(--tc); font-size: 13px; line-height: 1.5; z-index: 200; animation: toastIn .3s ease; box-shadow: 0 4px 20px rgba(0,0,0,.4); }
@keyframes toastIn { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
</style>
