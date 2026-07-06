<script setup>
import { ref } from 'vue'
import { sendMessage, useChat } from '../stores/chatStore.js'

const chat = useChat()
const text = ref('')

function send() {
  const m = text.value.trim()
  if (!m || chat.sending) return
  chat.messages.push({ role: 'user', content: m })
  chat.history.push({ role: 'user', content: m })
  sendMessage(m)
  text.value = ''
}
function key(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
}
</script>

<template>
  <div class="input-area">
    <div class="input-wrap">
      <textarea
        v-model="text"
        class="input"
        placeholder="输入消息…"
        rows="1"
        @keydown="key"
        :disabled="!chat.connected"
      ></textarea>
      <button class="send" :disabled="!text.trim() || !chat.connected" @click="send">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-area {
  padding: 10px 16px 14px;
  background: linear-gradient(180deg, transparent, rgba(8, 12, 24, 0.6));
}
.input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--bg-surface);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 4px 4px 4px 14px;
  transition: border-color 0.2s;
}
.input-wrap:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 20px var(--accent-glow);
}
.input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  font-family: var(--font-sans);
  font-size: 14px;
  color: var(--text);
  resize: none;
  line-height: 1.5;
  max-height: 100px;
  padding: 8px 0;
}
.input::placeholder { color: var(--text-tertiary); }
.send {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--accent-start), var(--accent-end));
  border: none;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
  box-shadow: 0 2px 12px var(--accent-glow);
}
.send:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 20px var(--accent-glow);
}
.send:disabled { opacity: 0.3; cursor: default; box-shadow: none; }
</style>
