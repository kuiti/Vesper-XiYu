// views/ChatView.vue — 聊天视图（控制器层）
<template>
  <div class="chat-page" :style="{ fontSize: chatFontSize + 'px' }">
    <div class="msg-list" ref="msgListRef" @scroll="onScroll">
      <div v-if="store.loadingMore" class="load-hint">加载中...</div>
      <div v-if="store.nextAfterId && !store.loadingMore" class="load-hint load-more" @click="store.loadMoreHistory()">点击加载更多</div>
      <div v-for="(msg, i) in store.messages" :key="msg.id || i" class="msg-row" :class="msg.role">
        <div class="msg-content" v-html="renderMsg(msg)"></div>
      </div>
      <div v-if="store.isStreaming && streamText" class="msg-row assistant">
        <div class="msg-content">{{ streamText }}<span class="cursor">▊</span></div>
      </div>
    </div>
    <div class="input-area">
      <input
        v-model="inputText"
        class="chat-input"
        placeholder="说点什么..."
        @keydown.enter.exact="send"
        :disabled="store.isStreaming"
      />
      <button class="send-btn" @click="send" :disabled="store.isStreaming || !inputText.trim()">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useChatStore } from '../stores/chat.js'
import { useUiStore } from '../stores/ui.js'

const store = useChatStore()
const ui = useUiStore()

const inputText = ref('')
const msgListRef = ref(null)
const chatFontSize = ref(14)
const streamText = ref('')

onMounted(() => {
  store.loadHistory()
  store.loadFavoriteIds()
  store.connect(onWsMessage)
})

onBeforeUnmount(() => {
  store.disconnect()
})

function onWsMessage(event) {
  let data
  try { data = JSON.parse(event.data) } catch(e) { return }
  if (data.type === 'token') {
    streamText.value += data.content
  } else if (data.type === 'done') {
    if (streamText.value) {
      store.messages.push({
        role: 'assistant',
        content: streamText.value,
        timestamp: new Date().toISOString(),
      })
      store.totalMessages++
      streamText.value = ''
    }
    store.isStreaming = false
    scrollToBottom()
  } else if (data.type === 'greeting') {
    store.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString(), _isGreeting: true })
    store.totalMessages++
    nextTick(() => scrollToBottom())
  } else if (data.type === 'error') {
    store.messages.push({ role: 'assistant', content: '错误：' + data.content, timestamp: new Date().toISOString() })
    store.isStreaming = false
  }
}

function send() {
  const text = inputText.value.trim()
  if (!text || store.isStreaming) return
  inputText.value = ''
  store.messages.push({ role: 'user', content: text, timestamp: new Date().toISOString() })
  store.totalMessages++
  store.isStreaming = true
  store.send({
    message: text,
    history: store.messages.slice(-35).map(m => ({ role: m.role, content: m.content })),
  })
  nextTick(() => scrollToBottom(true))
}

function scrollToBottom(smooth) {
  nextTick(() => {
    const el = msgListRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function onScroll() {
  const el = msgListRef.value
  if (el && el.scrollTop === 0 && store.nextAfterId && !store.loadingMore) {
    store.loadMoreHistory()
  }
}

function renderMsg(msg) {
  return msg.content.replace(/\n/g, '<br>')
}

watch(() => store.messages.length, () => nextTick(() => scrollToBottom()))
</script>

<style scoped>
.chat-page { display: flex; flex-direction: column; height: 100%; }
.msg-list { flex: 1; overflow-y: auto; padding: 16px; }
.msg-row { margin-bottom: 12px; }
.msg-row.user { text-align: right; }
.msg-content {
  display: inline-block; max-width: 75%; padding: 10px 14px;
  border-radius: 12px; font-size: 14px; line-height: 1.6;
  text-align: left; word-break: break-word;
}
.user .msg-content { background: var(--ub, #1d3557); color: #e2e8f0; border-bottom-right-radius: 4px; }
.assistant .msg-content { background: var(--ab, #181e2b); color: #e2e8f0; border-bottom-left-radius: 4px; }
.cursor { animation: blink 1s step-end infinite; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }
.load-hint { text-align: center; font-size: 12px; color: #7b8ca0; padding: 8px; }
.load-more { cursor: pointer; }
.load-more:hover { color: var(--p, #6a9fd8); }
.input-area { display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border, #252d3a); background: var(--bg, #0f1119); }
.chat-input {
  flex: 1; padding: 10px 14px; border: 1px solid var(--border, #252d3a);
  border-radius: 8px; background: var(--sb, #161927); color: #e2e8f0;
  font-size: 14px; outline: none;
}
.chat-input:focus { border-color: var(--p, #6a9fd8); }
.send-btn {
  padding: 10px 20px; border: none; border-radius: 8px;
  background: var(--p, #6a9fd8); color: #fff; font-size: 14px; cursor: pointer;
}
.send-btn:disabled { opacity: .4; cursor: not-allowed; }
</style>
