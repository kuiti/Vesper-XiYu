<script setup>
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { useChat, setFindNextSentence, setScrollToBottom, loadHistory, loadMoreHistory, toggleFav, setQuoteMsg, loadFavorites, sendMessage } from '../stores/chatStore.js'
import { sendFeedback, fetchActiveCharacter } from '../utils/api.js'
import MessageRow from '../components/MessageRow.vue'
import ChatInput from '../components/ChatInput.vue'

const chat = useChat()
const list = ref(null)
const searchOpen = ref(false)
const searchQuery = ref('')
const searchResults = ref([])
const searching = ref(false)
const affection = ref(null)
const trust = ref(null)
const emotion = ref('calm')

// Context menu
const ctxShow = ref(false)
const ctxX = ref(0)
const ctxY = ref(0)
const ctxTarget = ref(null)

// Edit sheet
const editShow = ref(false)
const editText = ref('')
let editMsgId = null

// TTS
let _audio = null

// ─── Find next sentence ───
function findNextSentence(text) {
  if (!text) return null
  const SENTENCE_END = /[。！？!?…～]/, GREEDY_END = /[…～]/
  const MIN_CHARS = 12
  let state = 0, buf = '', parenBuf = ''
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (state === 0) {
      if (ch === '（' || ch === '(') {
        if (buf.trim().length >= MIN_CHARS) return [buf.trim(), text.slice(i)]
        state = 1; parenBuf = buf + ch; buf = ''; continue
      }
      if (ch === '\n' && text[i+1] === '\n') { if (buf.trim()) return [buf.trim(), text.slice(i+2)]; i++; continue }
      buf += ch
      if (SENTENCE_END.test(ch)) {
        let end = i+1
        while (end < text.length && GREEDY_END.test(text[end])) { buf += text[end]; end++ }
        const s = buf.trim(); if (s.length >= MIN_CHARS) return [s, text.slice(end)]; continue
      }
    } else if (state === 1) {
      parenBuf += ch
      if (ch === '）' || ch === ')') { state = 2; if (i+1 < text.length && text[i+1] === '\n') { const s = parenBuf.trim(); if (s.length >= 2) return [s, text.slice(i+1)] } }
    } else if (state === 2) {
      if (ch === '（' || ch === '(') { const s = parenBuf.trim(); if (s.length >= 2) return [s, text.slice(i)]; parenBuf = ch; state = 1; continue }
      if (ch === '\n' && text[i+1] === '\n') { const s = parenBuf.trim(); if (s.length >= 2) return [s, text.slice(i+2)]; parenBuf = ''; state = 0; i++; continue }
      if (ch === '\n') { const s = parenBuf.trim(); if (s.length >= 2) return [s, text.slice(i+1)]; parenBuf = ''; state = 0; continue }
      parenBuf += ch
      if (SENTENCE_END.test(ch)) {
        let end = i+1
        while (end < text.length && GREEDY_END.test(text[end])) { parenBuf += text[end]; end++ }
        const s = parenBuf.trim(); if (s.length >= MIN_CHARS) { parenBuf = ''; state = 0; return [s, text.slice(end)] }
      }
    }
  }
  return null
}

setFindNextSentence(findNextSentence)
setScrollToBottom(() => { nextTick(() => { if (list.value) list.value.scrollTop = list.value.scrollHeight }) })

watch(() => chat.messages.length, () => { nextTick(() => { if (list.value) list.value.scrollTop = list.value.scrollHeight }) })

// Load history on mount
onMounted(async () => {
  await loadHistory()
  await loadFavorites()
  // Load avatars
  try {
    const d = await fetchActiveCharacter()
    if (d?.character) {
      chat.aiAvatarUrl = d.character.avatar ? `/avatars/${d.character.avatar}` : ''
      chat.userAvatarUrl = ''  // user avatar separate
    }
  } catch (_) {}
  fetchRel()
  setInterval(fetchRel, 60000)
})

async function fetchRel() {
  try {
    const r = await fetch('/emotion/relationship'); const d = await r.json()
    affection.value = d.affection ?? d.aff; trust.value = d.trust ?? d.tr; emotion.value = d.ai_emotion || 'calm'
  } catch (_) {}
}

// Search
async function doSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  try {
    const r = await fetch(`/search/chat?q=${encodeURIComponent(searchQuery.value)}&limit=20`)
    searchResults.value = await r.json() || []
  } catch (_) { searchResults.value = [] }
  searching.value = false
}
function jumpToMsg(id) { console.log('jump to', id) }

// Context menu
function openCtx(e, msg) { ctxX.value = e.clientX; ctxY.value = e.clientY; ctxTarget.value = msg; ctxShow.value = true }
function closeCtx() { ctxShow.value = false; ctxTarget.value = null }
function ctxCopy() { navigator.clipboard.writeText(ctxTarget.value?.content || '').catch(() => {}); closeCtx() }
function ctxQuote() { setQuoteMsg(ctxTarget.value); closeCtx() }
function ctxFav() { if (ctxTarget.value?.id) toggleFav(ctxTarget.value.id); closeCtx() }
const isLastAiMsg = computed(() => {
  const t = ctxTarget.value
  if (!t || t.role !== 'assistant') return false
  for (let i = chat.messages.length - 1; i >= 0; i--) {
    const m = chat.messages[i]
    if (m.role === 'assistant' && !m._sentenceFrag) return m === t
  }
  return false
})
function ctxReroll() { closeCtx(); if (!chat.sending) sendMessage('/reroll') }
async function ctxDelete() {
  const m = ctxTarget.value; closeCtx()
  if (!m?.id) return
  try { await fetch(`/chat/manage/message/${m.id}`, { method: 'DELETE' }) } catch (_) {}
}
function ctxEdit() {
  const m = ctxTarget.value; closeCtx()
  if (!m) return; editText.value = m.content || ''; editMsgId = m.id; editShow.value = true
}
async function confirmEdit() {
  const text = editText.value.trim(); const id = editMsgId
  editShow.value = false; editMsgId = null
  if (!text || !id) return
  if (chat.ws && chat.ws.readyState === 1) {
    chat.ws.send(JSON.stringify({ type: 'edit', msg_id: id, message: text }))
  }
}
function cancelEdit() { editShow.value = false; editMsgId = null }

// Feedback
async function handleFeedback(msg, score) {
  if (!msg?.id) return; msg._feedback = score
  try { await sendFeedback(msg.id, score) } catch (_) {}
}

// TTS
async function handleTTS(msg) {
  if (!msg?.content) return
  try {
    const r = await fetch('/tts/tts', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ text: msg.content, emotion_subtype: msg._emotion || 'neutral', score: 0, mode: 'preset' }) })
    const d = await r.json()
    if (d.success && d.audio_url) { if (_audio) _audio.pause(); _audio = new Audio(d.audio_url); _audio.play() }
  } catch (_) {}
}

// Keyboard
onMounted(() => {
  const handler = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); searchOpen.value = !searchOpen.value }
    if (e.key === 'End' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') { e.preventDefault(); if (list.value) list.value.scrollTop = list.value.scrollHeight }
  }
  document.addEventListener('keydown', handler)
  onUnmounted(() => document.removeEventListener('keydown', handler))
})

// Load more on scroll
function onScroll() {
  if (!list.value) return
  if (list.value.scrollTop < 40 && chat.nextAfterId && !chat.loadingMore) loadMoreHistory()
}

const estimatedTokens = computed(() => {
  let total = 0
  for (const m of chat.messages) {
    if (m.content) total += Math.ceil(m.content.length / 2)
  }
  return total
})

const chips = ['今天天气怎么样', '讲个笑话', '你最近过得如何', '帮我写段代码']
</script>

<template>
  <div class="chat" @click.right.prevent>
    <header class="topbar">
      <div class="tl">
        <div class="tlav">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/></svg>
        </div>
        <div>
          <div class="tln">夕语 AI</div>
          <div class="tls" :class="{ on: chat.connected }">
            <span class="tld"></span>{{ chat.connected ? '在线' : '离线' }}
            <span v-if="affection != null" class="rel">· 好感 {{ affection }} 信任 {{ trust }}</span>
          </div>
        </div>
      </div>
      <div class="tr">
        <span v-if="chat.messages.length" class="msg-count">{{ chat.messages.length }} 条 · ~{{ estimatedTokens.toLocaleString() }} tokens</span>
        <button class="tb" @click="searchOpen = !searchOpen" title="搜索 Ctrl+K">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        </button>
      </div>
    </header>

    <!-- Search overlay -->
    <div v-if="searchOpen" class="search-overlay" @click.self="searchOpen = false">
      <div class="search-panel">
        <div class="search-bar">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          <input v-model="searchQuery" class="si" placeholder="搜索聊天记录…" @keyup.enter="doSearch" autofocus />
          <button class="sbtn" @click="doSearch" :disabled="searching">{{ searching ? '搜索中…' : '搜索' }}</button>
        </div>
        <div v-if="searchResults.length" class="sr-list">
          <div v-for="r in searchResults" :key="r.id" class="sr-item" @click="jumpToMsg(r.id)">
            <div class="sr-role">{{ r.role === 'user' ? '你' : 'AI' }}</div>
            <div class="sr-text">{{ r.content?.slice(0, 120) }}</div>
          </div>
        </div>
        <div v-else-if="!searching" class="sr-empty">输入关键词搜索</div>
      </div>
    </div>

    <div class="msgs" ref="list" @scroll="onScroll" :style="{ fontSize: chat.fontSize + 'px' }">
      <div v-if="chat.loadingMore" class="loading-indicator">加载中...</div>

      <div v-if="!chat.messages.length && !chat.sending && chat.historyReady" class="empty">
        <div class="ei"><svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.15"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></div>
        <p class="e1">和夕语聊点什么吧</p>
        <p class="e2">发送消息 AI 将会回复 · Ctrl+K 搜索</p>
        <div class="chips">
          <span v-for="c in chips" :key="c" class="chip" @click="chat.messages.push({ role:'user', content:c }); chat.history.push({ role:'user', content:c }); chat.sending = true; sendMessage(c)">{{ c }}</span>
        </div>
      </div>

      <template v-for="(msg, i) in chat.messages" :key="i">
        <div v-if="msg.timestamp && (i === 0 || msg.timestamp.slice(0,10) !== (chat.messages[i-1]?.timestamp || '').slice(0,10))" class="date-sep">{{ msg.timestamp.slice(0, 10) }}</div>
        <MessageRow :msg="msg" :index="i" @feedback="handleFeedback" @tts="handleTTS" @ctxmenu="openCtx" />
      </template>

      <div v-if="chat.sending && !chat.messages.length" class="row assistant">
        <div class="av"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2a4 4 0 0 1 4 4c0 2-2 4-4 4s-4-2-4-4a4 4 0 0 1 4-4z"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/></svg></div>
        <div class="content"><div class="name">夕语</div><div class="bubble typing"><span class="d1"></span><span class="d2"></span><span class="d3"></span></div></div>
      </div>
    </div>

    <!-- Context menu -->
    <div v-if="ctxShow" class="ctx-menu" :style="{ left: ctxX + 'px', top: ctxY + 'px' }" @click.stop>
      <div class="ctx-item" @click="ctxCopy">复制</div>
      <div class="ctx-item" @click="ctxQuote">引用</div>
      <div class="ctx-item" @click="ctxFav">{{ chat.favoriteIds.has(ctxTarget?.id) ? '取消收藏' : '收藏' }}</div>
      <div class="ctx-item" @click="ctxEdit">编辑</div>
      <div v-if="isLastAiMsg" class="ctx-item" @click="ctxReroll">重新生成</div>
      <div class="ctx-item ctx-danger" @click="ctxDelete">删除</div>
    </div>

    <!-- Edit sheet -->
    <div v-if="editShow" class="edit-overlay" @click.self="cancelEdit">
      <div class="edit-panel">
        <div class="edit-title">编辑消息</div>
        <textarea v-model="editText" class="edit-ta" rows="4" @keydown.enter.ctrl="confirmEdit"></textarea>
        <div class="edit-acts">
          <button class="btn-ghost" @click="cancelEdit">取消</button>
          <button class="btn-primary" @click="confirmEdit">确认</button>
        </div>
      </div>
    </div>

    <ChatInput />
  </div>
</template>

<style scoped>
.chat { display:flex; flex-direction:column; height:100%; position:relative; }
.topbar { height:var(--topbar-h); padding:0 20px; background:var(--bg-glass); backdrop-filter:blur(12px); border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; flex-shrink:0; z-index:5; }
.tl { display:flex; align-items:center; gap:12px; }
.tlav { width:36px; height:36px; border-radius:var(--r-md); background:var(--accent-gradient); display:flex; align-items:center; justify-content:center; color:white; }
.tln { font-size:15px; font-weight:600; line-height:1.3; }
.tls { font-size:11px; color:var(--text-tertiary); display:flex; align-items:center; gap:4px; }
.tld { width:5px; height:5px; border-radius:50%; background:var(--text-tertiary); }
.tls.on { color:var(--success); } .tls.on .tld { background:var(--success); }
.rel { color:var(--accent); font-weight:500; }
.tr { display:flex; align-items:center; gap:8px; }
.msg-count { font-size:11px; color:var(--text-tertiary); }
.date-sep { text-align:center; font-size:11px; color:var(--text-tertiary); padding:12px 0 8px; }
.tb { width:32px; height:32px; border-radius:var(--r-sm); border:none; background:transparent; color:var(--text-muted); cursor:pointer; display:flex; align-items:center; justify-content:center; }
.tb:hover { background:var(--bg-hover); color:var(--text-secondary); }
.msgs { flex:1; overflow-y:auto; padding:12px 20px; display:flex; flex-direction:column; gap:2px; scrollbar-width:thin; scrollbar-color:var(--border) transparent; }
.loading-indicator { text-align:center; color:var(--text-muted); font-size:12px; padding:8px; }

.empty { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; color:var(--text-muted); padding:40px; }
.e1 { font-size:15px; font-weight:500; }
.e2 { font-size:12px; color:var(--text-tertiary); }
.chips { display:flex; gap:8px; flex-wrap:wrap; justify-content:center; margin-top:8px; }
.chip { padding:6px 14px; background:rgba(255,255,255,.04); border:1px solid var(--border); border-radius:16px; font-size:12px; color:var(--text-muted); cursor:pointer; transition:all .15s; }
.chip:hover { background:var(--accent); color:white; border-color:var(--accent); }

.typing { padding:10px 18px; display:flex; gap:5px; align-items:center; }
.typing span { display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--accent); animation:dotB 1.2s infinite; }
.typing .d2 { animation-delay:.15s; }
.typing .d3 { animation-delay:.3s; }
@keyframes dotB { 0%,60%,100% { opacity:.2; transform:translateY(0); } 30% { opacity:1; transform:translateY(-4px); } }

.ctx-menu { position:fixed; z-index:2000; background:var(--bg-sidebar); border:1px solid var(--border); border-radius:var(--r-md); box-shadow:0 4px 16px rgba(0,0,0,.4); overflow:hidden; min-width:110px; }
.ctx-item { padding:8px 16px; font-size:13px; color:var(--text); cursor:pointer; }
.ctx-item:hover { background:var(--bg-hover); }
.ctx-danger { color:#e74c3c; }

.edit-overlay { position:absolute; inset:0; background:rgba(0,0,0,0.5); z-index:10; display:flex; justify-content:center; padding-top:100px; }
.edit-panel { background:var(--bg-sidebar); border:1px solid var(--border); border-radius:var(--r-lg); width:440px; padding:16px; box-shadow:var(--shadow-lg); align-self:flex-start; }
.edit-title { font-size:14px; font-weight:600; margin-bottom:10px; }
.edit-ta { width:100%; background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-md); padding:10px; color:var(--text); font-size:14px; font-family:var(--font); outline:none; resize:none; }
.edit-ta:focus { border-color:var(--accent); }
.edit-acts { display:flex; gap:8px; justify-content:flex-end; margin-top:10px; }
.btn-ghost { padding:6px 14px; border:1px solid var(--border); background:transparent; color:var(--text-muted); border-radius:var(--r-sm); cursor:pointer; font-size:13px; }
.btn-primary { padding:6px 14px; border:none; background:var(--accent-gradient); color:white; border-radius:var(--r-sm); cursor:pointer; font-size:13px; }

.search-overlay { position:absolute; inset:0; background:rgba(0,0,0,0.5); z-index:10; display:flex; justify-content:center; padding-top:80px; }
.search-panel { background:var(--bg-sidebar); border:1px solid var(--border); border-radius:var(--r-lg); width:480px; max-height:400px; overflow:hidden; box-shadow:var(--shadow-lg); }
.search-bar { display:flex; align-items:center; gap:8px; padding:12px 14px; border-bottom:1px solid var(--border); color:var(--text-muted); }
.si { flex:1; background:none; border:none; outline:none; color:var(--text); font-family:var(--font); font-size:14px; }
.si::placeholder { color:var(--text-tertiary); }
.sbtn { padding:5px 12px; border-radius:var(--r-sm); border:none; background:var(--accent-gradient); color:white; font-size:12px; cursor:pointer; font-family:var(--font); }
.sbtn:disabled { opacity:0.5; }
.sr-list { max-height:300px; overflow-y:auto; }
.sr-item { padding:10px 14px; border-bottom:1px solid var(--border); cursor:pointer; }
.sr-item:hover { background:var(--bg-hover); }
.sr-role { font-size:11px; color:var(--accent); margin-bottom:2px; }
.sr-text { font-size:13px; color:var(--text-secondary); }
.sr-empty { padding:24px; text-align:center; color:var(--text-muted); font-size:13px; }
</style>
