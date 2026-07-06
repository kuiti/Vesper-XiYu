<script setup>
import { ref } from 'vue'
import { sendMessage, useChat, setQuoteMsg } from '../stores/chatStore.js'

const chat = useChat()
const text = ref('')

function send() {
  const m = text.value.trim()
  if (!m || chat.sending) return
  if (chat.quoteMsg) {
    const q = chat.quoteMsg
    const prefix = `（引用：${q.role === 'user' ? '用户' : 'AI'}说「${q.content.slice(0, 100)}」）\n`
    chat.messages.push({ role: 'user', content: prefix + m })
    chat.history.push({ role: 'user', content: prefix + m })
    setQuoteMsg(null)
  } else {
    chat.messages.push({ role: 'user', content: m })
    chat.history.push({ role: 'user', content: m })
  }
  sendMessage(m)
  text.value = ''
}

function onKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
}

function clearQuote() { setQuoteMsg(null) }
</script>

<template>
  <div class="input-area">
    <!-- Quote preview -->
    <div v-if="chat.quoteMsg" class="quote-bar">
      <div class="quote-line"></div>
      <div class="quote-body">
        <div class="quote-label">{{ chat.quoteMsg.role === 'user' ? '用户' : 'AI' }}</div>
        <div class="quote-text">{{ chat.quoteMsg.content.slice(0, 100) }}</div>
      </div>
      <button class="quote-close" @click="clearQuote">x</button>
    </div>

    <div class="input-box">
      <button class="tool-btn" title="附件">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
      </button>
      <textarea
        v-model="text"
        class="input-field"
        placeholder="输入消息…"
        rows="1"
        @keydown="onKey"
        :disabled="!chat.connected"
      ></textarea>
      <button class="send-btn" :disabled="!text.trim() || !chat.connected" @click="send" title="发送">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-area { padding: 8px 16px 14px; background:linear-gradient(0deg,var(--bg-chat) 0%,transparent 100%); }
.quote-bar { display:flex; align-items:stretch; gap:8px; margin-bottom:6px; padding:6px 8px; background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-md); }
.quote-line { width:3px; background:var(--accent); border-radius:2px; flex-shrink:0; }
.quote-body { flex:1; min-width:0; }
.quote-label { font-size:10px; color:var(--accent); margin-bottom:2px; }
.quote-text { font-size:12px; color:var(--text-muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.quote-close { background:none; border:none; color:var(--text-tertiary); cursor:pointer; font-size:14px; padding:0 2px; align-self:flex-start; }

.input-box { display:flex; align-items:flex-end; gap:6px; background:var(--bg-glass); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border:1px solid var(--border); border-radius:var(--r-lg); padding:4px; transition:border-color 0.2s,box-shadow 0.2s; }
.input-box:focus-within { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent),0 0 20px var(--accent-glow); }
.tool-btn { width:34px;height:34px; border-radius:var(--r-sm); border:none; background:transparent; color:var(--text-tertiary); cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; transition:all 0.12s; align-self:flex-end; margin-bottom:2px; }
.tool-btn:hover { color:var(--text-muted); background:var(--bg-hover); }
.input-field { flex:1; background:none; border:none; outline:none; font-family:var(--font); font-size:14px; color:var(--text); resize:none; line-height:1.5; max-height:90px; padding:8px 2px; }
.input-field::placeholder { color:var(--text-tertiary); }
.send-btn { width:36px;height:36px; border-radius:var(--r-md); background:var(--accent-gradient); border:none; color:white; cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; transition:all 0.15s; box-shadow:0 2px 8px var(--accent-glow); }
.send-btn:hover:not(:disabled) { transform:scale(1.05); box-shadow:0 4px 16px var(--accent-glow); }
.send-btn:active:not(:disabled) { transform:scale(0.95); }
.send-btn:disabled { opacity:0.25; cursor:default; box-shadow:none; }
</style>
