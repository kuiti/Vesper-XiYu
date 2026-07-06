<template>
  <div class="chat-container">
    <!-- Messages -->
    <div class="msg-list" ref="listRef" @scroll="onScroll">
      <div v-if="!messages.length && !chat.isStreaming" class="empty-state">
        <div class="empty-title">夕语</div>
        <div class="empty-sub">A character-driven roleplay engine</div>
      </div>

      <template v-for="(msg, idx) in messages" :key="msg.id || idx">
        <div v-if="showDateSep(msg, idx)" class="date-sep">{{ formatDate(msg.timestamp) }}</div>
        <div :class="['msg-row', msg.role, 'fade-in']">
          <div class="msg-avatar">
            <img v-if="msg.role === 'assistant' && avatarUrl" :src="avatarUrl" />
            <div v-else class="msg-avatar-fallback">{{ msg.role === 'user' ? userName[0] : aiName[0] }}</div>
          </div>
          <div class="msg-body">
            <div class="msg-meta">
              <span>{{ msg.role === 'assistant' ? aiName : userName }}</span>
              <span v-if="msg._emotion" class="emotion-dot" :style="{ background: emotionColor(msg._emotion) }"></span>
              <span>{{ fmtTime(msg.timestamp) }}</span>
            </div>
            <div v-if="msg.weatherData" class="msg-bubble">
              <WeatherCard :data="msg.weatherData" />
            </div>
            <div v-else class="msg-bubble" v-html="linkify(msg.content)" @contextmenu.prevent="onCtx($event, msg)"></div>
          </div>
        </div>
      </template>

      <!-- Streaming -->
      <div v-if="chat.isStreaming && chat.pendingReply" class="msg-row assistant fade-in">
        <div class="msg-avatar">
          <img v-if="avatarUrl" :src="avatarUrl" />
          <div v-else class="msg-avatar-fallback">{{ aiName[0] }}</div>
        </div>
        <div class="msg-body">
          <div class="msg-meta"><span>{{ aiName }}</span></div>
          <div class="msg-bubble">{{ chat.pendingReply }}</div>
        </div>
      </div>

      <div v-if="chat.isStreaming && !chat.pendingReply" class="msg-row assistant fade-in">
        <div class="msg-avatar">
          <img v-if="avatarUrl" :src="avatarUrl" />
          <div v-else class="msg-avatar-fallback">{{ aiName[0] }}</div>
        </div>
        <div class="msg-body">
          <div class="typing-indicator">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="input-area">
      <div class="input-wrapper">
        <textarea
          ref="inputRef"
          class="input-field"
          v-model="inputText"
          placeholder="Send a message..."
          @keydown.enter.exact.prevent="send"
          rows="1"
        ></textarea>
        <button class="send-btn" @click="send" :disabled="!inputText.trim() || chat.isStreaming">></button>
      </div>
      <div class="quick-bar" v-if="!messages.length">
        <span v-for="q in quickPhrases" :key="q" class="quick-chip" @click="sendQuick(q)">{{ q }}</span>
      </div>
    </div>

    <!-- Context Menu -->
    <div v-if="ctxMenu.show" class="ctx-menu" :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }">
      <div class="ctx-item" @click="ctxCopy">Copy</div>
      <div class="ctx-item" @click="ctxFav">{{ chat.favoriteIds.has(ctxMenu.msg?.id) ? 'Unfavorite' : 'Favorite' }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useChatStore } from '../stores/chatStore.js'
import { useAppStore } from '../stores/appStore.js'
import WeatherCard from './WeatherCard.vue'

const chat = useChatStore()
const app = useAppStore()

const inputText = ref('')
const listRef = ref(null)
const inputRef = ref(null)

const messages = computed(() => chat.messages)
const aiName = computed(() => app.activeCharacter?.name || app.settings.ai_name || 'AI')
const userName = computed(() => app.settings.user_name || 'User')
const avatarUrl = computed(() => app.activeCharacter?.avatar ? `/avatars/${app.activeCharacter.avatar}` : '')
const quickPhrases = ['Hello', 'Tell me a story', 'How are you today?']

const ctxMenu = ref({ show: false, x: 0, y: 0, msg: null })

function send() {
  if (!inputText.value.trim() || chat.isStreaming) return
  chat.sendMessage(inputText.value)
  inputText.value = ''
  nextTick(() => scrollToBottom())
}

function sendQuick(q) {
  chat.sendMessage(q)
  nextTick(() => scrollToBottom())
}

function scrollToBottom() {
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
}

function onScroll() {}

function showDateSep(msg, idx) {
  if (!msg.timestamp) return false
  if (idx === 0) return true
  const prev = messages.value[idx - 1]
  return msg.timestamp.slice(0, 10) !== (prev?.timestamp || '').slice(0, 10)
}

function formatDate(ts) {
  if (!ts) return ''
  return ts.slice(0, 10)
}

function fmtTime(ts) {
  if (!ts) return ''
  return ts.slice(11, 16)
}

function emotionColor(e) {
  const map = { happy: '#4ade80', sad: '#60a5fa', angry: '#f87171', surprise: '#fbbf24', love: '#f472b6', calm: '#7a8a9a' }
  return map[e] || '#7a8a9a'
}

function linkify(text) {
  if (!text) return ''
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/(https?:\/\/[^\s<>]+)/g, '<a href="$1" target="_blank">$1</a>')
}

function onCtx(e, msg) {
  ctxMenu.value = { show: true, x: e.clientX, y: e.clientY, msg }
}

function ctxCopy() {
  navigator.clipboard.writeText(ctxMenu.value.msg?.content || '')
  ctxMenu.value.show = false
}

function ctxFav() {
  if (ctxMenu.value.msg) chat.toggleFavorite(ctxMenu.value.msg)
  ctxMenu.value.show = false
}

function closeCtx() { ctxMenu.value.show = false }

onMounted(() => {
  document.addEventListener('click', closeCtx)
  watch(() => chat.messages.length, () => nextTick(scrollToBottom))
})

onUnmounted(() => {
  document.removeEventListener('click', closeCtx)
})
</script>
