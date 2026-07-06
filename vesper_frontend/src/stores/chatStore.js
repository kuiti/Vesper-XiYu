import { reactive } from 'vue'
import { fetchHistory, fetchFavorites, toggleFavorite as apiToggleFav, deleteFavorite } from '../utils/api.js'

const state = reactive({
  connected: false,
  messages: [],
  sending: false,
  emotion: 'calm',
  characters: [],
  history: [],
  pendingReply: '',
  sentenceMode: 'auto',
  schedId: null,
  nextAfterId: null,
  loadingMore: false,
  historyReady: false,
  favoriteIds: new Set(),
  aiAvatarUrl: '',
  userAvatarUrl: '',
  fontSize: parseInt(localStorage.getItem('vesper_font_size')) || 14,
  quoteMsg: null,
  _twQueue: [],
  _twActive: false,
  _twTimer: null,
  _streamTimeout: null,
  _findNextSentence: null,
  _scrollToBottom: null,
  _onDone: null,
})

let ws = null
let retry = null

export function connect() {
  if (ws) return
  const p = location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${p}//${location.host}/ws/chat`)
  ws.onopen = () => { state.connected = true }
  ws.onclose = () => { state.connected = false; ws = null; retry = setTimeout(connect, 3000) }
  ws.onerror = () => { stopTypewriter(); ws?.close(); ws = null }
  ws.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data)
      switch (d.type) {
        case 'token':
          push(d.content)
          break
        case 'done':
          finalize()
          state.sending = false
          if (d.emotion) state.emotion = d.emotion
          if (state._onDone) state._onDone(d)
          break
        case 'greeting':
          state.messages.push({ role: 'assistant', content: d.content })
          break
        case 'proactive':
          state.messages.push({ role: 'assistant', content: d.content, isProactive: true })
          break
        case 'reroll_start':
          if (state.schedId) { clearTimeout(state.schedId); state.schedId = null }
          state.pendingReply = ''
          state.sending = true
          break
        case 'error':
          state.sending = false
          state.messages.push({ role: 'assistant', content: '错误：' + d.content })
          stopTypewriter()
          break
      }
    } catch (_) {}
  }
}

let buf = ''

function push(t) {
  buf += t
  if (buf.length > 50000) return
  if (!state.schedId) schedulePop()
  const last = state.messages[state.messages.length - 1]
  if (last?.streaming) last.content = buf
  else state.messages.push({ role: 'assistant', content: buf, streaming: true })

  clearTimeout(state._streamTimeout)
  state._streamTimeout = setTimeout(() => {
    if (state.sending) {
      state.sending = false
      stopTypewriter()
      if (state.pendingReply) {
        state.messages.push({ role: 'assistant', content: state.pendingReply + '\n(回复被中断)', timestamp: new Date().toISOString() })
        state.pendingReply = ''
      }
    }
  }, 60000)
}

function schedulePop() {
  if (state.schedId) return
  const pop = () => {
    state.schedId = null
    state.pendingReply = state.pendingReply.replace(/^[\s\n]+/, '')
    if (!state.pendingReply) return
    if (state.sentenceMode === 'raw') { state.pendingReply = ''; state.sending = false; return }
    const result = state._findNextSentence ? state._findNextSentence(state.pendingReply) : null
    if (result) {
      const [sentence, rest] = result
      state.pendingReply = rest || ''
      if (state.sentenceMode === 'typewriter') { _twPush(sentence) }
      else {
        const frag = { role: 'assistant', content: sentence, timestamp: new Date().toISOString(), _sentenceFrag: true }
        state.messages.push(frag)
      }
      if (state._scrollToBottom) state._scrollToBottom()
      const jitter = 0.8 + Math.random() * 0.4
      const delay = Math.min(Math.max(300, 250 + sentence.length * 30), 2000) * jitter
      state.schedId = setTimeout(pop, delay | 0)
    } else if (!state.sending) {
      const remain = state.pendingReply.trim()
      if (state.sentenceMode === 'typewriter' && remain) { _twPush(remain) }
      else if (remain) {
        state.messages.push({ role: 'assistant', content: remain, timestamp: new Date().toISOString() })
      }
      state.pendingReply = ''
      if (state._scrollToBottom) state._scrollToBottom()
    } else {
      state.schedId = setTimeout(pop, 100)
    }
  }
  state.schedId = setTimeout(pop, 60)
}

function _twPush(sentence) {
  state._twQueue.push(sentence)
  if (!state._twActive) { state._twActive = true; _twTick() }
}

function _twTick() {
  if (!state._twQueue.length) { state._twActive = false; return }
  let sentence = state._twQueue[0]
  const msgs = state.messages
  let last = msgs[msgs.length - 1]
  if (!last || last.role !== 'assistant' || last._twDone) {
    last = { role: 'assistant', content: '', timestamp: new Date().toISOString(), _twDone: false }
    msgs.push(last)
  }
  last.content += sentence[0] || ''
  sentence = sentence.slice(1)
  state._twQueue[0] = sentence
  if (sentence.length === 0) {
    state._twQueue.shift()
    last._twDone = true
    if (state._scrollToBottom) state._scrollToBottom()
  }
  state._twTimer = setTimeout(() => _twTick(), 30 + Math.random() * 20)
}

function stopTypewriter() {
  state.sending = false
  clearTimeout(state._streamTimeout)
  if (state._twTimer) { clearTimeout(state._twTimer); state._twTimer = null }
  while (state._twQueue.length) {
    const s = state._twQueue.shift()
    const last = state.messages[state.messages.length - 1]
    if (!last || last.role !== 'assistant' || last._twDone) {
      state.messages.push({ role: 'assistant', content: s, timestamp: new Date().toISOString() })
    } else { last.content = last.content + s; last._twDone = true }
  }
  state._twActive = false
  if (state.schedId) { clearTimeout(state.schedId); state.schedId = null }
  if (state.pendingReply.trim()) schedulePop()
}

function finalize() {
  const last = state.messages[state.messages.length - 1]
  if (last?.streaming) { last.streaming = false; state.history.push({ role: 'assistant', content: last.content }) }
  buf = ''
  stopTypewriter()
}

export function sendMessage(text) {
  if (!ws || ws.readyState !== WebSocket.OPEN || !text.trim()) return
  state.sending = true
  state.pendingReply = ''
  ws.send(JSON.stringify({ message: text, history: state.history }))
}

export function setFindNextSentence(fn) { state._findNextSentence = fn }
export function setScrollToBottom(fn) { state._scrollToBottom = fn }
export function setOnDone(fn) { state._onDone = fn }
export function setSentenceMode(mode) { state.sentenceMode = mode }

export async function loadHistory() {
  try {
    const d = await fetchHistory(40)
    const msgs = d.messages || []
    state.messages = msgs
    state.nextAfterId = d.next_after_id || null
    state.historyReady = true
  } catch (_) {}
}

export async function loadMoreHistory() {
  if (!state.nextAfterId || state.loadingMore) return
  state.loadingMore = true
  try {
    const d = await fetchHistory(30, state.nextAfterId)
    const older = d.messages || []
    state.messages = [...older, ...state.messages]
    state.nextAfterId = d.next_after_id || null
  } catch (_) {}
  state.loadingMore = false
}

export async function toggleFav(msgId) {
  if (state.favoriteIds.has(msgId)) {
    try { await deleteFavorite(msgId); state.favoriteIds.delete(msgId) } catch (_) {}
  } else {
    try { await apiToggleFav(msgId); state.favoriteIds.add(msgId) } catch (_) {}
  }
}

export async function loadFavorites() {
  try {
    const f = await fetchFavorites()
    state.favoriteIds = new Set((f || []).map(x => x.msg_id))
  } catch (_) {}
}

export function setFontSize(px) {
  state.fontSize = px
  try { localStorage.setItem('vesper_font_size', px) } catch (_) {}
}

export function setQuoteMsg(msg) { state.quoteMsg = msg }

export function disconnect() {
  if (retry) clearTimeout(retry)
  if (ws) { ws.onclose = null; ws.close(); ws = null }
  state.connected = false
}

export function useChat() { return state }
