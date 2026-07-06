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
          :ipCity="ipCity" :ipCityShort="ipCityShort" :totalMessages="totalMessages" :kaomojis="kaomojis" :historyReady="historyReady"
          :voiceSettings="{ tts_enabled: allSettings.tts_enabled, tts_engine: allSettings.tts_engine, auto_play: allSettings.auto_play_voice, tts_clone_audio: allSettings.tts_clone_audio, tts_clone_mode: allSettings.tts_clone_mode }"
          :characterVoice="characterVoice"
          @send="sendMessage" @toggle-favorite="toggleFavorite"
          @context-menu-action="onContextMenuAction"
          @load-more="loadMoreHistory" @delete-message="onDeleteMessage"
          @clear-today-learning="todayLearning = null"
          @feedback="onFeedback"
        />

        <Transition name="page-fade" mode="out-in">
          <ToolsView v-if="activeView==='tools'" :aiName="aiNameLocal" :key="'tools'" />
          <DiaryView v-else-if="activeView==='diary'" :aiName="aiNameLocal" :key="'diary'" />
          <GamesView v-else-if="activeView==='games'" @game-event="onGameEvent" @ai-help="onAiHelp" :aiName="aiNameLocal" :key="'games'" />
          <StatsView v-else-if="activeView==='stats'" :key="'stats'" />
          <MemoryView v-else-if="activeView==='memory'" :aiName="aiNameLocal" :key="'memory'" />
          <CharactersView v-else-if="activeView==='characters'" :key="'characters'" />
          <SettingsView v-else-if="activeView==='settings'" :key="'settings'"
            :settings="allSettings" :themeLocal="themeLocal" :ipCity="ipCity"
            :relationship="relationship" :emotionTrend="emotionTrend"
            :totalMessages="totalMessages" :conversationDays="conversationDays"
            :assistantAvatarUrl="assistantAvatarUrl" :userAvatarUrl="userAvatarUrl"
            @config-changed="onSettingsChanged" @export-chat="exportChat"
            @close="activeView='chat'"
          />
          <HistoryView v-else-if="activeView==='history'" :key="'history'"
            :favoriteIds="favoriteIds" :aiName="aiNameLocal" :userName="userNameLocal"
            @close="activeView='chat'" @toggle-favorite="toggleFavorite"
          />
        </Transition>
      </div>
    </div>
  </div>

  <div v-if="confirmDialog.show" class="confirm-overlay" @click.self="resolveConfirm(false)">
    <div class="confirm-box"><div class="confirm-msg">{{ confirmDialog.msg }}</div>
      <div class="confirm-btns"><button class="btn" @click="resolveConfirm(true)">确定</button><button class="btn-s" @click="resolveConfirm(false)">取消</button></div>
    </div>
  </div>
</template>

<script>
import { mapState, mapActions } from 'pinia'
import { useUiStore } from './stores/uiStore'
import { useSettingsStore } from './stores/settingsStore'
import { useChatStore } from './stores/chatStore'
import api from './api'
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
import CharactersView from './components/CharactersView.vue'
import FloatingCalendar from './components/FloatingCalendar.vue'

export default {
  components: { NavBar, ChatView, ToolsView, StatsView, GamesView, MemoryView, SettingsView, LockScreen, OnboardingWizard, AchievementToast, HistoryView, DiaryView, CharactersView, FloatingCalendar, LoginView },
  provide() { return { showConfirm: this.showConfirm } },
  data() {
    return {
      assistantAvatarUrl: '', userAvatarUrl: '',
      relationship: {}, emotionTrend: [], ipCity: '', ipCityShort: '',
      favoriteIds: new Set(), quickReplies: ['展开说说', '换个角度', '好的', '继续'],
      _reconnectMsg: null, _unmounted: false,
      _locationTimer: null, _mediaDark: null, _wheelHandler: null,
      characterVoice: null,
    }
  },
  computed: {
    ...mapState(useUiStore, ['activeView', 'showOnboarding', 'showLockScreen', 'needLogin',
      'confirmDialog', 'achievementPopup', 'gameToast', 'pinEnabled', 'pinCode']),
    ...mapState(useSettingsStore, ['allSettings', 'currentTheme', 'themeLocal', 'aiNameLocal',
      'userNameLocal', 'chatFontSize', 'chatBgImage', 'bgOpacity', 'bgBlur', 'bgMode', 'sentenceMode', 'quickPhrases']),
    ...mapState(useChatStore, ['ws', 'wsReady', 'messages', 'totalMessages',
      'isStreaming', 'pendingReply', 'nextAfterId', 'loadingMore', 'todayLearning', 'timelineDates', 'historyReady']),
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
    const chatStore = useChatStore()
    const uiStore = useUiStore()
    const settingsStore = useSettingsStore()

    // 注入 chatStore 回调（替代 $refs 依赖）
    chatStore._onGreeting = (data) => {
      const last = chatStore.messages[chatStore.messages.length - 1]
      if (!last || (last.role === 'assistant' && !last.isProactive && !last._isGreeting) || last.role === 'user') {
        chatStore.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString(), _isGreeting: true })
        chatStore.totalMessages++
      }
    }
    chatStore._onProactive = (data) => {
      const last2 = chatStore.messages.slice(-2)
      if (!last2.some(m => m.role === 'assistant' && m.isProactive)) {
        chatStore.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString(), isProactive: true })
        chatStore.totalMessages++
      }
    }
    chatStore._onWeather = (data) => {
      chatStore.messages.push({ role: 'assistant', content: '__WEATHER_CARD__', weatherData: data.data, timestamp: new Date().toISOString(), isWeather: true })
      chatStore.totalMessages++
    }
    chatStore._onSurprise = (data) => {
      chatStore.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString(), isSurprise: true })
      chatStore.totalMessages++
    }
    chatStore._onDone = () => { this.$refs.floatingCalendar?.loadSchedules?.() }
    chatStore._scrollToBottom = (instant) => { this.$nextTick(() => this.$refs.chatView?.scrollToBottom(instant)) }
    chatStore._findNextSentence = (text) => this.$refs.chatView?.findNextSentence?.(text)
    chatStore._autoPlayTTS = (msg) => { this.$refs.chatView?.autoPlayTTS(msg) }

    // 云端模式：检查是否需要登录
    const cfg = window.__SAKURA_CONFIG__ || {}
    if (!!cfg.backendHost) {
      if (!localStorage.getItem('sakura_api_token')) { uiStore.needLogin = true; return }
    }

    await settingsStore.loadAllSettings()
    try {
      if (localStorage.getItem('_reset_pin') === '1') {
        localStorage.removeItem('_reset_pin')
        await api.post('/settings/', { key: 'pin_code', value: '' })
        await api.post('/settings/', { key: 'pin_enabled', value: false })
      }
    } catch (e) {}
    this._checkOnboarding()
    this.loadAvatars(); this.loadFavoriteIds()
    chatStore.loadHistory(); this.loadTodayLearning(); this.loadTimelineDates()
    uiStore.maybeShowLockScreen(settingsStore.pinEnabled, settingsStore.pinCode)
    chatStore.connectWebSocket()
    this.loadRelationship(); this.loadEmotionTrend(); this.loadIpLocation(); this.loadCharacterVoice()
    this._locationTimer = setInterval(() => { if (!this._unmounted && document.visibilityState === 'visible') this.loadIpLocation() }, 300000)
    if (Notification.permission === 'default') Notification.requestPermission()
    this._mediaDark = window.matchMedia('(prefers-color-scheme: dark)')
    this._mediaDark.addEventListener('change', this._onSystemThemeChange)
    document.addEventListener('keydown', this._keydownHandler)
    this._wheelHandler = (e) => { if (e.ctrlKey) { e.preventDefault(); useSettingsStore().chatFontSize = Math.min(20, Math.max(10, useSettingsStore().chatFontSize + (e.deltaY > 0 ? 1 : -1))) } }
    document.addEventListener('wheel', this._wheelHandler, { passive: false })
  },
  beforeUnmount() {
    this._unmounted = true
    const cs = useChatStore()
    if (cs.ws) { cs.ws.onclose = null; cs.ws.onerror = null; cs.ws.close() }
    clearTimeout(this._locationTimer); clearInterval(this._locationTimer)
    document.removeEventListener('keydown', this._keydownHandler)
    if (this._wheelHandler) document.removeEventListener('wheel', this._wheelHandler)
    if (this._mediaDark) this._mediaDark.removeEventListener('change', this._onSystemThemeChange)
  },
  methods: {
    ...mapActions(useUiStore, ['navigate', 'showConfirm', 'resolveConfirm', 'showAchievement', 'showToast', 'unlock']),
    ...mapActions(useSettingsStore, ['loadAllSettings', 'applySetting']),
    ...mapActions(useChatStore, ['connectWebSocket', 'sendMessage', 'loadHistory', 'loadMoreHistory', 'stopTypewriter']),

    async onLoginSuccess(token) {
      const ui = useUiStore(); const ss = useSettingsStore(); const cs = useChatStore()
      ui.needLogin = false
      await ss.loadAllSettings()
      this._checkOnboarding(); this.loadAvatars(); this.loadFavoriteIds()
      cs.loadHistory(); this.loadTodayLearning(); this.loadTimelineDates()
      this.loadRelationship(); this.loadEmotionTrend()
      cs.connectWebSocket(); this.loadIpLocation()
    },
    onNav(view) { useUiStore().activeView = view; if (this.$refs.chatView) this.$refs.chatView.showCtx = false },
    onScrollBottom() { this.$refs.chatView?.forceScrollToBottom() },
    onDeleteMessage(id) { const cs = useChatStore(); cs.messages = cs.messages.filter(m => m.id !== id); cs.totalMessages = cs.messages.length },
    onFeedback({ msgId, score }) { const cs = useChatStore(); if (cs.ws && cs.wsReady) cs.ws.send(JSON.stringify({ type: 'feedback', msg_id: msgId, score })) },
    _onSystemThemeChange() {},
    onSettingsChanged(key, value) {
      const ss = useSettingsStore()
      ss.applySetting(key, value)
      if (key === 'precise_city') { this.ipCity = value; const parts = value.split('·'); this.ipCityShort = parts[parts.length - 1] || value }
      else if (key === 'avatar_updated') { this.loadAvatars() }
    },
    showDisconnectToast() { this._reconnectMsg = { show: true, text: '连接已断开，正在重连...' }; setTimeout(() => { if (this._reconnectMsg) this._reconnectMsg.show = false }, 8000) },
    manualReconnect() { const cs = useChatStore(); cs.wsReconnectAttempts = 0; clearTimeout(cs._reconnectTimer); cs._reconnectTimer = null; cs.connectWebSocket() },
    isMsgFavorite(msg) { return msg && msg.id && this.favoriteIds.has(msg.id) },
    async toggleFavorite(msg) { if (!msg?.id) return; try { if (this.favoriteIds.has(msg.id)) { await api.delete(`/favorites/${msg.id}`); this.favoriteIds.delete(msg.id) } else { await api.post(`/favorites/${msg.id}`); this.favoriteIds.add(msg.id) } } catch (e) {} },
    async loadFavoriteIds() { try { const res = await api.get('/favorites'); this.favoriteIds = new Set((res.data || []).map(f => f.msg_id)) } catch (e) {} },
    onContextMenuAction(action, msg) {
      if (action === 'toggle-favorite') this.toggleFavorite(msg)
      else if (action === 'reroll-from' && msg?.id) {
        const cs = useChatStore()
        if (!cs.wsReady) return
        const idx = cs.messages.findIndex(m => m.id === msg.id)
        if (idx !== -1) { cs.messages = cs.messages.slice(0, idx); cs.totalMessages = cs.messages.length }
        cs.isStreaming = true; cs.pendingReply = ''; cs._currentReplyLen = 0
        cs.ws.send(JSON.stringify({ message: `/reroll_from:${msg.id}`, history: cs.messages.filter(m => !m._sentenceFrag).slice(-35).map(m => ({ role: m.role, content: m.content })) }))
      }
    },
    async loadTodayLearning() { try { const res = await api.get('/memory/today-learning'); if (res.data?.has_new) useChatStore().todayLearning = res.data } catch (e) {} },
    async loadTimelineDates() { try { const res = await api.get('/chat/history/dates'); const months = res.data?.months || []; useChatStore().timelineDates = months.flatMap(m => (m.dates || []).map(d => d.date)) } catch (e) {} },
    async loadAvatars() { try { const r1 = await api.get('/avatar/assistant'); if (r1.data?.url) this.assistantAvatarUrl = r1.data.url } catch (e) {}; try { const r2 = await api.get('/avatar/user'); if (r2.data?.url) this.userAvatarUrl = r2.data.url } catch (e) {} },
    async loadIpLocation() { try { const res = await api.get('/location/ip'); if (res.data?.city) { if (!useSettingsStore().allSettings.precise_city) { this.ipCity = res.data.city; this.ipCityShort = res.data.city } api.post('/settings/', { key: 'manual_city', value: res.data.city }).catch(() => {}) } } catch (e) {} },
    async loadRelationship() { try { const res = await api.get('/relationship/'); this.relationship = res.data } catch (e) {} },
    async loadCharacterVoice() { try { const res = await api.get('/characters/active'); const ch = res.data?.character; this.characterVoice = ch?.voice || null } catch (e) {} },
    async loadEmotionTrend() { try { const res = await api.get('/emotion/trend?days=14'); this.emotionTrend = res.data || [] } catch (e) {} },
    sendSystemMessage(msg) {
      const cs = useChatStore()
      if (!cs.wsReady || cs.isStreaming) return
      cs.isStreaming = true; cs.pendingReply = ''; cs._currentReplyLen = 0
      cs.ws.send(JSON.stringify({ message: msg, history: cs.messages.filter(m => !m._sentenceFrag && !m._gameEvent && !m._isGreeting && !m.isProactive).slice(-3).map(m => ({ role: m.role, content: m.content })), _system: true }))
      clearTimeout(cs._streamTimeout)
      cs._streamTimeout = setTimeout(() => { if (cs.isStreaming) { cs.isStreaming = false; cs.stopTypewriter() } }, 15000)
    },
    onAiHelp(evt) { if (!evt) return; this.sendSystemMessage(this.aiNameLocal + '救我！我正玩' + evt.game + '呢，快帮帮我！') },
    onGameEvent(evt) {
      if (!evt || useChatStore().isStreaming) return
      const map = { high_score: '刷新了最高分', game_won: '通关了', game_lost: '输了', reached_2048: '合出了2048', game_over: '游戏结束' }
      const act = map[evt.type] || evt.type
      let msg = evt.game + '：' + act + '！'
      if (evt.score) msg += '得分' + evt.score
      if (evt.difficulty) msg += '，' + ({easy:'简单',medium:'中等',hard:'困难'}[evt.difficulty]||evt.difficulty)
      this.sendSystemMessage(msg)
    },
    async exportChat(fmt) {
      const format = fmt || 'txt'
      try { const res = await api.get(`/export/chat?format=${format}`); const blob = new Blob([res.data.content], { type: format === 'md' ? 'text/markdown' : 'text/plain' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = res.data.filename; a.click(); URL.revokeObjectURL(url) }
      catch (e) { alert('导出失败') }
    },
    _checkOnboarding() {
      api.get('/settings/onboarding-status').then(res => { if (res.data?.needs_onboarding) useUiStore().showOnboarding = true }).catch(() => {})
    },
    onOnboardingCompleted() { useUiStore().showOnboarding = false; useSettingsStore().loadAllSettings(); useChatStore().connectWebSocket() },
    _keydownHandler(e) {
      const ui = useUiStore()
      const tag = document.activeElement?.tagName; const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
      if (e.key === 'Escape') { if (this.$refs.chatView) this.$refs.chatView.showCtx = false; ui.showEmojiPicker = false }
      else if ((e.ctrlKey || e.metaKey) && !isInput) {
        const viewMap = { '1': 'chat', '2': 'tools', '3': 'stats', '4': 'memory', '5': 'settings', '6': 'games' }
        if (viewMap[e.key]) { e.preventDefault(); ui.activeView = viewMap[e.key] }
        else if (e.key === 'n' || e.key === 'N') {
          e.preventDefault()
          ui.showConfirm('⚠️ 确定要清空所有聊天记录吗？此操作不可恢复。').then(ok => {
            if (ok) { api.delete('/chat/manage/all').then(() => { const cs = useChatStore(); cs.messages = []; cs.totalMessages = 0; cs.nextAfterId = null }).catch(() => {}) }
          })
        }
      }
    },
  },
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; scrollbar-width: none; }
*::-webkit-scrollbar { display: none; }
input, select, textarea, button { font-family: inherit; }
select { appearance: none; -webkit-appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23888' d='M6 8L1 3h10z'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 10px center; padding-right: 28px; }
.del-btn { background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 11px; padding: 2px 4px; opacity: .4; transition: opacity .15s,color .15s; }
.del-btn:hover { opacity: 1; color: #e74c3c; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--surface-app, #0f1119); color: var(--text-primary, #e2e8f0); overflow: hidden; height: 100dvh; }
.app { display: flex; height: 100dvh; width: 100vw; }
.app-layout { display: flex; flex: 1; height: 100dvh; overflow: hidden; }
.main-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
.main-area::after { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent, var(--accent-muted), transparent); opacity: .5; z-index: 1; }
.reconnect-banner { display: flex; align-items: center; justify-content: space-between; padding: 6px 16px; background: rgba(248,81,73,.15); border-bottom: 1px solid rgba(248,81,73,.3); color: var(--text-primary); font-size: 13px; z-index: 100; }
.reconnect-btn { padding: 4px 12px; background: var(--accent-primary, #5390d4); color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; }
.reconnect-btn:hover { filter: brightness(1.1); }
@media (max-width: 768px) {
  .app-layout { flex-direction: column; }
  .main-area { padding-bottom: 64px; }
  .confirm-box { min-width: 0; max-width: 90vw; margin: 0 16px; }
  .game-toast { right: 16px; left: 16px; max-width: none; }
}
[data-theme="vesper"] .main-area::before { content: ''; position: absolute; inset: 0; z-index: 0; pointer-events: none; background-image: radial-gradient(1px 1px at 3% 10%, rgba(196,184,232,.7), transparent), radial-gradient(1.5px 1.5px at 7% 55%, rgba(155,143,184,.5), transparent), radial-gradient(1px 1px at 11% 28%, rgba(196,184,232,.4), transparent), radial-gradient(2px 2px at 15% 78%, rgba(155,143,184,.6), transparent), radial-gradient(1px 1px at 22% 8%, rgba(196,184,232,.5), transparent), radial-gradient(1.5px 1.5px at 28% 45%, rgba(155,143,184,.4), transparent), radial-gradient(1px 1px at 33% 68%, rgba(196,184,232,.6), transparent), radial-gradient(1px 1px at 38% 15%, rgba(155,143,184,.3), transparent), radial-gradient(2px 2px at 42% 52%, rgba(196,184,232,.5), transparent), radial-gradient(1px 1px at 48% 80%, rgba(155,143,184,.4), transparent), radial-gradient(1.5px 1.5px at 53% 22%, rgba(196,184,232,.6), transparent), radial-gradient(1px 1px at 58% 62%, rgba(155,143,184,.4), transparent), radial-gradient(1px 1px at 63% 38%, rgba(196,184,232,.3), transparent), radial-gradient(2px 2px at 68% 72%, rgba(155,143,184,.5), transparent), radial-gradient(1px 1px at 73% 5%, rgba(196,184,232,.5), transparent), radial-gradient(1.5px 1.5px at 78% 48%, rgba(155,143,184,.4), transparent), radial-gradient(1px 1px at 83% 85%, rgba(196,184,232,.6), transparent), radial-gradient(1px 1px at 88% 18%, rgba(155,143,184,.3), transparent), radial-gradient(2px 2px at 93% 55%, rgba(196,184,232,.5), transparent), radial-gradient(1px 1px at 97% 75%, rgba(155,143,184,.4), transparent); animation: vesper-twinkle 5s ease-in-out infinite alternate; }
@keyframes vesper-twinkle { 0% { opacity: .4; } 50% { opacity: .7; } 100% { opacity: .5; } }
[data-theme="sakura"] .main-area::before { content: ''; position: absolute; inset: 0; z-index: 0; pointer-events: none; background-image: radial-gradient(2px 3px at 5% 15%, rgba(232,146,155,.45), transparent), radial-gradient(2px 2px at 12% 45%, rgba(143,188,143,.25), transparent), radial-gradient(3px 2px at 20% 8%, rgba(232,146,155,.4), transparent), radial-gradient(2px 3px at 25% 65%, rgba(232,146,155,.35), transparent), radial-gradient(2px 2px at 32% 32%, rgba(143,188,143,.2), transparent), radial-gradient(3px 2px at 38% 78%, rgba(232,146,155,.45), transparent), radial-gradient(2px 3px at 45% 12%, rgba(143,188,143,.25), transparent), radial-gradient(2px 2px at 52% 52%, rgba(232,146,155,.4), transparent), radial-gradient(3px 2px at 58% 85%, rgba(232,146,155,.35), transparent), radial-gradient(2px 3px at 65% 22%, rgba(143,188,143,.25), transparent), radial-gradient(2px 2px at 72% 58%, rgba(232,146,155,.45), transparent), radial-gradient(3px 2px at 78% 5%, rgba(232,146,155,.4), transparent), radial-gradient(2px 3px at 85% 42%, rgba(143,188,143,.2), transparent), radial-gradient(2px 2px at 90% 72%, rgba(232,146,155,.35), transparent), radial-gradient(3px 2px at 95% 25%, rgba(232,146,155,.45), transparent), radial-gradient(2px 3px at 8% 92%, rgba(143,188,143,.25), transparent), radial-gradient(2px 2px at 42% 95%, rgba(232,146,155,.35), transparent), radial-gradient(3px 2px at 68% 92%, rgba(143,188,143,.2), transparent); animation: sakura-float 8s ease-in-out infinite alternate; }
@keyframes sakura-float { 0% { opacity: .35; transform: translateY(0); } 100% { opacity: .55; transform: translateY(-4px); } }
.confirm-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 3000; display: flex; align-items: center; justify-content: center; }
.confirm-box { background: var(--surface-sidebar); border: 1px solid var(--border-default); border-radius: 12px; padding: 24px; min-width: 300px; max-width: 420px; box-shadow: 0 8px 32px rgba(0,0,0,.4); }
.confirm-msg { font-size: 14px; color: var(--text-primary); margin-bottom: 16px; line-height: 1.6; }
.confirm-btns { display: flex; gap: 8px; justify-content: flex-end; }

/* ─── 通用页面视图布局 ─── */
.page-view { flex: 1; display: flex; flex-direction: column; overflow-y: auto; overflow-x: hidden; }
.page-view::-webkit-scrollbar { display: none; }
.page-body { padding: 0 32px 32px; display: flex; flex-direction: column; gap: 16px; }
.page-card { background: var(--surface-card); border: 1px solid var(--border-default); border-radius: 10px; padding: 20px; transition: border-color .2s; }
.page-card:hover { border-color: var(--accent-muted); }
.page-card h3 { font-size: 14px; font-weight: 600; color: var(--text-primary); margin: 0 0 12px; letter-spacing: .01em; }
.page-card.compact { padding: 14px; }
.page-card.compact h3 { margin-bottom: 8px; font-size: 12px; }
.page-card .hint { font-size: 12px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 12px; }
.page-card .field { margin-bottom: 12px; }
.page-card .field label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; font-weight: 500; }
.page-card .field input, .page-card .field select { width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border-default); background: var(--surface-app); color: var(--text-primary); font-size: 13px; box-sizing: border-box; transition: border-color .2s; }
.page-card .field input:focus, .page-card .field select:focus { outline: none; border-color: var(--accent-primary); }
.btn { padding: 8px 18px; background: var(--accent-primary); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all .15s; }
.btn:hover { filter: brightness(1.15); transform: translateY(-1px); }
.btn:active { transform: translateY(0); }
.btn-s { padding: 6px 12px; background: rgba(255,255,255,.04); border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-secondary); cursor: pointer; font-size: 12px; transition: all .15s; }
.btn-s:hover { border-color: var(--accent-primary); color: var(--accent-primary); background: var(--accent-muted); }
.ok { color: var(--status-success); font-size: 12px; }
.fail { color: var(--status-error); font-size: 12px; }
.page-hint { color: var(--text-secondary); font-size: 12px; text-align: center; padding: 12px; line-height: 1.5; }

/* ─── 页面切换过渡 ─── */
.page-fade-enter-active, .page-fade-leave-active { transition: opacity .15s ease, transform .15s ease; }
.page-fade-enter-from { opacity: 0; transform: translateY(6px); }
.page-fade-leave-to { opacity: 0; }
</style>
