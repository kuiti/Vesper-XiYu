<template>
  <div class="chat-view">
    <TodayLearning v-if="todayLearning" :data="todayLearning" @close="$emit('clear-today-learning')" />

    <div class="chat-top-bar">
      <span class="ctb-rel" v-if="affection != null" title="好感度/信任度">好感 {{ affection }} · 信任 {{ trust }}</span>
      <span class="ctb-sep" v-if="affection != null && totalMessages">·</span>
      <span class="ctb-msg-count" v-if="totalMessages">{{ totalMessages }} 条消息</span>
      <span class="ctb-sep" v-if="totalMessages && reminderCount">·</span>
      <span class="ctb-reminder" v-if="reminderCount">{{ reminderCount }} 提醒</span>
      <span class="ctb-sep" v-if="(totalMessages || reminderCount) && ipCity">·</span>
      <span class="ctb-location" v-if="ipCity">({{ ipCityShort || ipCity }})</span>
    </div>

    <div class="msg-list" ref="container" @scroll="onScroll" :style="{ fontSize: (chatFontSize || 14) + 'px' }">
      <div v-if="loadingMore" class="loading-indicator">加载中...</div>

      <div v-if="!messages.length && !isStreaming && historyReady" class="empty-chat">
        <div class="empty-greeting">{{ timeGreeting }}</div>
        <div class="empty-hint">和{{ aiNameLocal || '佐仓' }}聊点什么吧</div>
        <div class="empty-chips">
          <span v-for="c in suggestionChips" :key="c" class="empty-chip" @click="$emit('send', c)">{{ c }}</span>
        </div>
      </div>

      <div v-for="(msg, idx) in messages" :key="msg.id || idx">
        <div v-if="dateSep(msg, idx)" class="date-sep" :data-date="(msg.timestamp || '').slice(0,10)">{{ dateSep(msg, idx) }}</div>
        <div :class="['msg', msg.role, { proactive: msg.isProactive, surprise: msg.isSurprise }]">
          <img class="msg-avatar" :src="msg.role === 'user' ? userAvatarUrl : assistantAvatarUrl" />
          <div class="msg-body">
            <div class="msg-name">{{ msg.role === 'user' ? (userNameLocal || '我') : (aiNameLocal || '佐仓') }}</div>
            <div v-if="(msg.isWeather || isWeatherContent(msg.content)) && (msg.weatherData || parseWeatherContent(msg.content))" class="weather-msg"><WeatherCard :data="msg.weatherData || parseWeatherContent(msg.content)" /></div>
            <div v-else class="msg-bubbles">
              <div v-for="(para, pi) in splitParagraphs(msg.content)" :key="pi" class="msg-bubble" v-html="safeLinkify(para)" @contextmenu.prevent="openCtx($event, msg)" @dblclick="copyText(msg.content)"></div>
            </div>
            <div class="msg-footer">
              <span class="msg-time">{{ fmtTime(msg.timestamp) }}</span>
              <button v-if="msg.role === 'assistant' && msg.content && voiceSettings?.tts_enabled" class="tts-btn" @click="speakText(msg)" :title="ttsPlaying && ttsMsgId === msg.id ? '停止' : '朗读'">
                <svg v-if="ttsLoading && ttsMsgId === msg.id" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="spin"><circle cx="12" cy="12" r="10" stroke-dasharray="50 20"/></svg>
                <svg v-else-if="ttsPlaying && ttsMsgId === msg.id" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="11,5 6,9 2,9 2,15 6,15 11,19"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
              </button>
              <div v-if="msg.role === 'assistant' && msg.id && !msg._feedback" class="feedback-btns">
                <button class="fb-btn" @click="sendFeedback(msg, 1)" title="赞">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
                </button>
                <button class="fb-btn" @click="sendFeedback(msg, -1)" title="踩">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10zM17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
                </button>
              </div>
              <span v-if="msg._feedback === 1" class="fb-done fb-liked">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
              </span>
              <span v-if="msg._feedback === -1" class="fb-done fb-disliked">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10zM17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
              </span>
            </div>
          </div>
        </div>
      </div>
      <div v-if="isStreaming && !(sentenceMode === 'typewriter' && messages.length && messages[messages.length-1].role === 'assistant' && !messages[messages.length-1]._twDone)" class="msg assistant">
        <img class="msg-avatar" :src="assistantAvatarUrl" />
        <div class="msg-body">
          <div class="msg-name">{{ aiNameLocal || '佐仓' }}</div>
          <div class="msg-bubble typing-dots"><span class="dot-bounce"></span><span class="dot-bounce"></span><span class="dot-bounce"></span></div>
        </div>
      </div>
    </div>

    <div v-if="showCtx" class="context-menu" :style="{ left: ctxX + 'px', top: ctxY + 'px' }" @click.stop>
      <div class="ctx-item" @click="ctxCopy">复制</div>
      <div class="ctx-item" @click="ctxFavorite">{{ isFav(ctxTarget) ? '取消收藏' : '收藏' }}</div>
      <div class="ctx-item ctx-danger" @click="ctxDelete">删除</div>
    </div>

    <ChatInput :input="inputText" :quickPhrases="quickPhrases" :quoteMsg="quoteMsg" :kaomojis="kaomojis"
      @update:input="inputText = $event" @send="onSend" @clear-quote="quoteMsg = null" />
  </div>
</template>

<script>
import api from '../api'
import WeatherCard from './WeatherCard.vue'
import ChatInput from './ChatInput.vue'
import TodayLearning from './TodayLearning.vue'

export default {
  components: { WeatherCard, ChatInput, TodayLearning },
  props: {
    ws: Object, wsReady: Boolean, messages: Array, isStreaming: Boolean,
    pendingReply: String, aiNameLocal: String, userNameLocal: String,
    assistantAvatarUrl: String, userAvatarUrl: String, quickPhrases: Array,
    favoriteIds: Set, sentenceMode: String, quickReplies: Array,
    todayLearning: Object, timelineDates: Array, nextAfterId: String, loadingMore: Boolean, floatingDate: String,
    ipCity: String, ipCityShort: String, totalMessages: Number, reminderCount: Number, chatFontSize: Number, kaomojis: Array, historyReady: Boolean,
    voiceSettings: Object,
  },
  emits: ['send', 'toggle-favorite', 'context-menu-action', 'load-more', 'delete-message', 'clear-today-learning'],
  computed: { timeGreeting() { const h = new Date().getHours(); if (h < 6) return '夜深了'; if (h < 9) return '早上好'; if (h < 12) return '上午好'; if (h < 14) return '中午好'; if (h < 18) return '下午好'; if (h < 21) return '晚上好'; return '夜深了' } },
  data() {
    return {
      inputText: '', showCtx: false, ctxX: 0, ctxY: 0, ctxTarget: null,
      suggestionChips: ['今天天气怎么样', '讲个笑话', '你最近过得如何', '帮我写段代码'],
      quoteMsg: null, userScrolledUp: false, _blockLoadMore: false,
      affection: null, trust: null, _now: Date.now(),
      // TTS state
      ttsPlaying: false, ttsLoading: false, ttsMsgId: null, _audio: null,
      _ttsQueue: [], _ttsProcessing: false
    }
  },
  methods: {
    async fetchRelationship() { try { const res = await api.get('/relationship/'); this.affection = res.data.affection; this.trust = res.data.trust } catch (e) {} },
    safeLinkify(t) { if (!t) return ''; const parts=[]; const urlRe=/(https?:\/\/[^\s<>]+)/gi; let last=0; let m; while((m=urlRe.exec(t))!==null){ if(m.index>last) parts.push(t.slice(last,m.index).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')); parts.push('<a href=\"'+m[1].replace(/&/g,'&amp;').replace(/"/g,'&quot;')+'\" target=\"_blank\">'+m[1].replace(/&/g,'&amp;')+'</a>'); last=urlRe.lastIndex } if(last<t.length) parts.push(t.slice(last).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')); return parts.join('') },
    fmtTime(ts) { if (!ts) return ''; const d = new Date(ts); if (isNaN(d.getTime())) return ''; const now = new Date(this._now); const diffMs = now - d; const diffMin = Math.floor(diffMs / 60000); if (diffMin < 1) return '刚刚'; if (diffMin < 60) return diffMin + '分钟前'; if (d.toDateString() === now.toDateString()) { const h = String(d.getHours()).padStart(2,'0'); const m = String(d.getMinutes()).padStart(2,'0'); return h + ':' + m }; const yesterday = new Date(now); yesterday.setDate(now.getDate() - 1); if (d.toDateString() === yesterday.toDateString()) { const h = String(d.getHours()).padStart(2,'0'); const m = String(d.getMinutes()).padStart(2,'0'); return '昨天 ' + h + ':' + m }; const h = String(d.getHours()).padStart(2,'0'); const m = String(d.getMinutes()).padStart(2,'0'); return (d.getMonth()+1) + '/' + d.getDate() + ' ' + h + ':' + m },
    dateSep(msg, idx) {
      if (!msg.timestamp) return ''
      if (idx === 0) return msg.timestamp.slice(0, 10)
      const prev = this.messages[idx - 1]
      if (!prev || !prev.timestamp) return ''
      const a = msg.timestamp.slice(0, 10), b = prev.timestamp.slice(0, 10)
      return a !== b ? a : ''
    },
    showQuickReplies(msg, idx) {
      return false  // 隐藏预设快捷回复
    },
    sendFeedback(msg, score) {
      if (!msg?.id) return
      msg._feedback = score
      this.$emit('feedback', { msgId: msg.id, score })
    },
    // ── TTS 语音播放 ──
    async speakText(msg) {
      if (!msg?.content) return
      // 如果正在播放同一条，停止
      if (this.ttsPlaying && this.ttsMsgId === msg.id) { this.stopSpeech(); return }
      this.stopSpeech()
      await this._doSpeak(msg)
    },
    async _doSpeak(msg) {
      this.ttsLoading = true
      this.ttsMsgId = msg.id || msg.content?.slice(0, 20)
      try {
        const mode = this.voiceSettings?.tts_clone_mode || 'preset'
        const res = await api.post('/tts/tts', {
          text: msg.content,
          emotion_subtype: msg._emotion || 'neutral',
          score: msg._score || 0,
          mode: mode,
        })
        if (res.data?.success && res.data?.audio_url) {
          await new Promise((resolve) => {
            const audio = new Audio(res.data.audio_url)
            this._audio = audio
            audio.onplay = () => { this.ttsPlaying = true; this.ttsLoading = false }
            audio.onended = () => { this.ttsPlaying = false; this.ttsMsgId = null; this._audio = null; resolve() }
            audio.onerror = () => { this.ttsPlaying = false; this.ttsLoading = false; this.ttsMsgId = null; this._audio = null; resolve() }
            audio.play().catch(() => resolve())
          })
        } else {
          this.ttsLoading = false; this.ttsMsgId = null
        }
      } catch (e) {
        this.ttsLoading = false; this.ttsMsgId = null
      }
    },
    // 自动播放（流式结束后调用）
    autoPlayTTS(msg) {
      if (!this.voiceSettings?.tts_enabled || !this.voiceSettings?.auto_play) return
      if (!msg?.content || msg.role !== 'assistant') return
      this._ttsQueue.push(msg)
      this._processTTSQueue()
    },
    async _processTTSQueue() {
      if (this._ttsProcessing) return
      this._ttsProcessing = true
      while (this._ttsQueue.length > 0) {
        const msg = this._ttsQueue.shift()
        if (msg?.content && this.voiceSettings?.tts_enabled && this.voiceSettings?.auto_play) {
          await this._doSpeak(msg)
        }
      }
      this._ttsProcessing = false
    },
    stopSpeech() {
      this._ttsQueue = []
      this._ttsProcessing = false
      if (this._audio) { this._audio.pause(); this._audio.currentTime = 0; this._audio = null }
      this.ttsPlaying = false
      this.ttsMsgId = null
    },
    // autoPlayTTS 已移除重复定义，使用上文行165的队列版本
    isWeatherContent(c) { return typeof c === 'string' && c.startsWith('__WEATHER_CARD__') },
    parseWeatherContent(c) { try { return JSON.parse(c.replace('__WEATHER_CARD__', '')) } catch (e) { return null } },
    copyText(t) { navigator.clipboard.writeText(t).catch(() => {}) },
    splitParagraphs(text) {
      if (!text) return ['']
      return text.split(/\n{2,}/).filter(Boolean)
    },
    findNextSentence(text) {
      if (this.sentenceMode === 'raw') return null
      if (this.sentenceMode === 'delimiter') { const idx = text.indexOf('<<>>'); if (idx !== -1) return [text.slice(0, idx), text.slice(idx + 4)] }
      const SENTENCE_END = /[。！？!?…～]/, GREEDY_END = /[…～]/
      const MIN_CHARS = 12  // 短句不拆分，合并到下一句
      let state = 0, buf = '', parenBuf = ''
      for (let i = 0; i < text.length; i++) {
        const ch = text[i]
        if (state === 0) {
          if (ch === '（' || ch === '(') { if (buf.trim().length >= MIN_CHARS) return [buf.trim(), text.slice(i)]; state = 1; parenBuf = buf + ch; buf = ''; continue }
          if (ch === '\n' && text[i+1] === '\n') { if (buf.trim()) return [buf.trim(), text.slice(i+2)]; i++; continue }
          buf += ch
          if (SENTENCE_END.test(ch)) { let end = i+1; while (end < text.length && GREEDY_END.test(text[end])) { buf += text[end]; end++ }; const s = buf.trim(); if (s.length >= MIN_CHARS) return [s, text.slice(end)]; continue }
        } else if (state === 1) { parenBuf += ch; if (ch === '）' || ch === ')') { state = 2; if (i+1 < text.length && text[i+1] === '\n') { const s = parenBuf.trim(); if (s.length >= 2) return [s, text.slice(i+1)] } } }
        else if (state === 2) {
          if (ch === '（' || ch === '(') { const s = parenBuf.trim(); if (s.length >= 2) return [s, text.slice(i)]; parenBuf = ch; state = 1; continue }
          if (ch === '\n' && text[i+1] === '\n') { const s = parenBuf.trim(); if (s.length >= 2) return [s, text.slice(i+2)]; parenBuf = ''; state = 0; i++; continue }
          if (ch === '\n') { const s = parenBuf.trim(); if (s.length >= 2) return [s, text.slice(i+1)]; parenBuf = ''; state = 0; continue }
          parenBuf += ch
          if (SENTENCE_END.test(ch)) { let end = i+1; while (end < text.length && GREEDY_END.test(text[end])) { parenBuf += text[end]; end++ }; const s = parenBuf.trim(); if (s.length >= MIN_CHARS) { parenBuf = ''; state = 0; return [s, text.slice(end)] } }
        }
      }
      return null
    },
    scrollToBottom(force) { if (!force && this.userScrolledUp) return; if (force) this._blockLoadMore = true; this.$nextTick(() => { requestAnimationFrame(() => { const el = this.$refs.container; if (el) el.scrollTop = el.scrollHeight; if (force) setTimeout(() => { this._blockLoadMore = false }, 800) }) }) },
    forceScrollToBottom() { this.userScrolledUp = false; this.scrollToBottom(true) },
    _onKeyDown(e) { if (e.key === 'End' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') { e.preventDefault(); this.forceScrollToBottom() } },
    onScroll() { const el = this.$refs.container; if (!el) return; this.userScrolledUp = el.scrollTop + el.clientHeight < el.scrollHeight - 60; if (el.scrollTop < 40 && this.nextAfterId && !this.loadingMore && !this._blockLoadMore) this.$emit('load-more') },
    onSend(msg) { if (!msg || !this.wsReady) return; const ctx = this.quoteMsg; if (ctx) { msg = `（引用：${ctx.role === 'user' ? '用户' : 'AI'}说「${ctx.content.slice(0, 100)}」）\n` + msg; this.quoteMsg = null } this.$emit('send', msg); this.inputText = '' },
    openCtx(e, msg) { e.preventDefault(); this.ctxX = e.clientX; this.ctxY = e.clientY; this.ctxTarget = msg; this.showCtx = true; if (this._ctxListener) document.removeEventListener('click', this._ctxListener); this._ctxListener = () => { this.showCtx = false; this._ctxListener = null }; document.addEventListener('click', this._ctxListener, { once: true }) },
    ctxCopy() { navigator.clipboard.writeText(this.ctxTarget?.content || '').catch(() => {}); this.showCtx = false },
    ctxQuote() { this.quoteMsg = this.ctxTarget; this.showCtx = false },
    isFav(m) { return m?.id && this.favoriteIds?.has(m.id) },
    ctxFavorite() { if (this.ctxTarget) this.$emit('toggle-favorite', this.ctxTarget); this.showCtx = false },
    ctxReroll() { if (this.ctxTarget?.id) { this.$emit('context-menu-action', 'reroll-from', this.ctxTarget); this.showCtx = false } },
    async ctxDelete() { const m = this.ctxTarget; this.showCtx = false; if (!m?.id) return; try { await api.delete(`/chat/manage/message/${m.id}`); this.$emit('delete-message', m.id) } catch (e) {} },
  },
  mounted() {
    this.fetchRelationship()
    this._relTimer = setInterval(() => this.fetchRelationship(), 60000)
    this._timeTimer = setInterval(() => { this._now = Date.now() }, 60000)
    document.addEventListener('keydown', this._onKeyDown)
  },
  beforeUnmount() {
    if (this._relTimer) { clearInterval(this._relTimer); this._relTimer = null }
    if (this._timeTimer) { clearInterval(this._timeTimer); this._timeTimer = null }
    document.removeEventListener('keydown', this._onKeyDown)
    if (this._ctxListener) { document.removeEventListener('click', this._ctxListener); this._ctxListener = null }
    if (this._statusTimer) { clearTimeout(this._statusTimer) }
  },
}
</script>

<style scoped>
.chat-view { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
.chat-top-bar { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 4px 16px; background: var(--surface-sidebar); border-bottom: 1px solid var(--border-default); font-size: 11px; color: var(--text-secondary); flex-shrink: 0; }
.ctb-sep { color: var(--text-secondary); opacity: .4; }
.ctb-rel { color: var(--accent-primary); font-weight: 500; }
.ctb-msg-count { color: var(--text-secondary); }
.ctb-reminder { color: var(--text-secondary); }
.ctb-location { color: var(--text-secondary); }
.msg-list { flex: 1; overflow-y: auto; padding: 16px 20px; display: flex; flex-direction: column; gap: 16px; scroll-behavior: smooth; position: relative; scrollbar-width: none; }
.msg-list::-webkit-scrollbar { display: none; }
.msg-list::before { content: ''; position: fixed; inset: 0; background-image: var(--chat-bg-img); background-size: var(--bg-mode, cover); background-position: center; opacity: var(--bg-opacity, 1); filter: blur(var(--bg-blur, 0px)); z-index: 0; pointer-events: none; }
.msg { display: flex; gap: 10px; position: relative; z-index: 1; }
.msg.user { flex-direction: row-reverse; }
.msg-avatar { width: 36px; height: 36px; border-radius: 4px; flex-shrink: 0; object-fit: cover; }
.msg-body { max-width: 70%; }
.msg-name { font-size: 11px; color: var(--text-secondary); margin-bottom: 4px; }
.msg.user .msg-name { text-align: right; }
.msg-bubble { padding: 10px 14px; border-radius: 8px; font-size: 14px; line-height: 1.6; word-break: break-word; background: var(--bubble-assistant); color: var(--text-primary); }
.msg.user .msg-bubble { background: var(--bubble-user); }
.msg-bubbles { display: flex; flex-direction: column; gap: 3px; align-items: flex-start; }
.msg-bubbles .msg-bubble { max-width: 100%; }
.msg.user .msg-bubbles { align-items: flex-end; }
.msg-bubbles .msg-bubble:not(:first-child) { border-top-left-radius: 4px; border-top-right-radius: 4px; }
.msg-bubbles .msg-bubble:not(:last-child) { border-bottom-left-radius: 4px; border-bottom-right-radius: 4px; }
.msg-bubble a { color: var(--accent-primary); }
.msg-bubble.streaming { opacity: .8; }
.msg-bubble.typing-dots { padding: 10px 18px; display: flex; gap: 5px; align-items: center; }
.dot-bounce { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--accent-primary); animation: dotBounce 1.2s infinite; }
.dot-bounce:nth-child(2) { animation-delay: .15s; }
.dot-bounce:nth-child(3) { animation-delay: .3s; }
@keyframes dotBounce { 0%,60%,100% { opacity: .2; transform: translateY(0); } 30% { opacity: 1; transform: translateY(-6px); } }
.msg.proactive .msg-bubble { border-left: 2px solid var(--accent-primary); opacity: .85; }
.msg.surprise .msg-bubble { border: 1px solid rgba(255,255,255,.1); }
.msg-footer { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
.msg-time { font-size: 10px; color: var(--text-secondary); }
.msg.user .msg-footer { justify-content: flex-end; }
.feedback-btns { display: flex; gap: 6px; }
.fb-btn { background: none; border: none; cursor: pointer; color: var(--text-secondary); opacity: 0.5; transition: all .15s; padding: 2px; display: flex; align-items: center; }
.fb-btn:hover { opacity: 1; color: var(--accent-primary); }
.tts-btn { background: none; border: none; cursor: pointer; color: var(--text-secondary); opacity: 0.5; transition: all .15s; padding: 2px; display: flex; align-items: center; }
.tts-btn:hover { opacity: 1; color: var(--accent-primary); }
@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 1s linear infinite; }
.fb-done { display: flex; align-items: center; }
.fb-liked { color: var(--accent-primary); opacity: 0.6; }
.fb-disliked { color: #e74c3c; opacity: 0.5; }
.empty-chat { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 40px; }
.empty-greeting { font-size: 24px; color: var(--text-primary); font-weight: 300; letter-spacing: 2px; }
.empty-hint { font-size: 13px; color: var(--text-secondary); }
.empty-chips { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-top: 8px; }
.empty-chip { padding: 6px 14px; background: rgba(255,255,255,.04); border: 1px solid var(--border-default); border-radius: 16px; font-size: 12px; color: var(--text-secondary); cursor: pointer; transition: all .15s; }
.empty-chip:hover { background: var(--accent-primary); color: #fff; border-color: var(--accent-primary); }
/* bubble tails - only on last paragraph */
.msg.user .msg-bubbles .msg-bubble:last-child { position: relative; }
.msg.user .msg-bubbles .msg-bubble:last-child::after { content: ''; position: absolute; bottom: 0; right: -6px; width: 0; height: 0; border-left: 6px solid var(--bubble-user); border-top: 6px solid transparent; border-bottom: 6px solid transparent; }
.msg.assistant .msg-bubbles .msg-bubble:last-child { position: relative; }
.msg.assistant .msg-bubbles .msg-bubble:last-child::after { content: ''; position: absolute; bottom: 0; left: -6px; width: 0; height: 0; border-right: 6px solid var(--bubble-assistant); border-top: 6px solid transparent; border-bottom: 6px solid transparent; }
.date-sep { text-align: center; font-size: 11px; color: var(--text-secondary); padding: 8px 0; }
.loading-indicator { text-align: center; color: var(--text-secondary); font-size: 12px; padding: 8px; }
.quick-replies { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; }
.qr-chip { padding: 3px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border-default); border-radius: 12px; font-size: 11px; color: var(--text-secondary); cursor: pointer; }
.qr-chip:hover { background: var(--accent-primary); color: #fff; border-color: var(--accent-primary); }
.timeline-bar { position: absolute; right: 4px; top: 0; bottom: 0; width: 60px; overflow-y: auto; padding: 4px 0; z-index: 5; scrollbar-width: none; }
.timeline-bar::-webkit-scrollbar { display: none; }
.tl-close { text-align: center; font-size: 12px; color: var(--text-secondary); cursor: pointer; padding: 2px 0; opacity: .4; transition: opacity .15s; }
.tl-close:hover { opacity: 1; color: #e74c3c; }
.tl-date { padding: 3px 6px; font-size: 10px; color: var(--text-secondary); cursor: pointer; text-align: center; border-radius: 3px; }
.tl-date:hover { background: rgba(255,255,255,.06); color: var(--text-primary); }
.context-menu { position: fixed; z-index: 2000; background: var(--surface-app); border: 1px solid var(--border-default); border-radius: 6px; box-shadow: 0 4px 16px rgba(0,0,0,.4); overflow: hidden; min-width: 120px; }
.ctx-item { padding: 8px 16px; font-size: 13px; color: var(--text-primary); cursor: pointer; }
.ctx-item:hover { background: rgba(255,255,255,.04); }
.ctx-danger { color: #e74c3c; }

/* 移动端适配 */
@media (max-width: 768px) {
  .fb-btn, .tts-btn {
    padding: 8px;
    min-width: 44px;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0.5;
  }
  .ctx-item {
    padding: 12px 16px;
    font-size: 14px;
    min-height: 44px;
    display: flex;
    align-items: center;
  }
  .msg-body { max-width: 85%; }
  .msg-list { padding: 12px 12px; }
  .chat-top-bar { padding: 8px 12px; font-size: 12px; }
}
</style>
