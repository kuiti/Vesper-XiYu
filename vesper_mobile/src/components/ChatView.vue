<template>
  <div class="chat-container" @touchstart="onTouchStart" @touchend="onTouchEnd">
    <!-- Messages -->
    <div class="msg-list" ref="listRef" @scroll="onScroll">
      <!-- Loading -->
      <div v-if="chat.isLoading" class="loading-state">
        <div class="loading-spinner"></div>
      </div>

      <!-- Empty -->
      <div v-if="!messages.length && !chat.isLoading && !chat.isStreaming" class="empty-state">
        <div class="empty-avatar">
          <img v-if="avatarUrl" :src="avatarUrl" />
          <div v-else class="avatar-fallback-lg">{{ aiName[0] }}</div>
        </div>
        <div class="empty-title">{{ aiName }}</div>
        <div class="empty-sub">{{ charDesc || '开始对话吧' }}</div>
        <div class="quick-actions">
          <button v-for="q in quickPhrases" :key="q" class="quick-btn" @click="sendQuick(q)">{{ q }}</button>
        </div>
      </div>

      <!-- Network Error -->
      <div v-if="!chat.wsReady && !chat.isLoading && messages.length > 0" class="network-banner">
        <span>连接已断开，正在重连...</span>
      </div>

      <!-- Command Input -->
      <Transition name="fade">
        <div v-if="showCmdInput" class="cmd-overlay" @click.self="showCmdInput = false">
          <div class="cmd-box">
            <input
              class="cmd-field"
              v-model="cmdText"
              placeholder="/help, /reroll, /reset..."
              @keydown.enter="execCmd"
              @keydown.escape="showCmdInput = false"
              ref="cmdRef"
            />
            <div class="cmd-hints">
              <span v-for="c in cmdHints" :key="c.cmd" class="cmd-hint" @click="execCmdDirect(c.cmd)">
                <span class="cmd-name">{{ c.cmd }}</span>
                <span class="cmd-desc">{{ c.desc }}</span>
              </span>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Pull indicator -->
      <div v-if="pullDistance > 0" class="pull-indicator" :style="{ height: pullDistance + 'px' }">
        <div class="pull-spinner" :class="{ active: pullDistance > 60 }"></div>
      </div>

      <!-- Message List -->
      <template v-for="(msg, idx) in messages" :key="msg.id || idx">
        <div v-if="showDateSep(msg, idx)" class="date-sep">
          <span>{{ formatDate(msg.timestamp) }}</span>
        </div>
        <div :class="['msg-row', msg.role, { 'fade-in': isNewMsg(idx), proactive: msg.isProactive, surprise: msg.isSurprise }]">
          <div v-if="msg.role === 'assistant'" class="msg-avatar">
            <img v-if="avatarUrl" :src="avatarUrl" />
            <div v-else class="avatar-fallback">{{ aiName[0] }}</div>
          </div>
          <div class="msg-bubble" @click="onMsgTap($event, msg)">
            <div v-if="msg.role === 'user'" class="msg-sender">{{ userName }}</div>
            <img v-if="msg._image" :src="'data:image/png;base64,' + msg._image" class="msg-image" />
            <div class="msg-text" v-html="linkify(msg.content)"></div>
            <div class="msg-footer">
              <span class="msg-time">{{ fmtTime(msg.timestamp) }}</span>
              <span v-if="msg._emotion" class="emotion-dot" :style="{ background: emotionColor(msg._emotion) }"></span>
            </div>
          </div>
        </div>
      </template>

      <!-- Streaming -->
      <div v-if="chat.isStreaming" class="msg-row assistant">
        <div class="msg-avatar">
          <img v-if="avatarUrl" :src="avatarUrl" />
          <div v-else class="avatar-fallback">{{ aiName[0] }}</div>
        </div>
        <div class="msg-bubble streaming">
          <div v-if="chat.pendingReply" class="msg-text">{{ chat.pendingReply }}<span class="cursor-blink"></span></div>
          <div v-else class="typing-dots"><span></span><span></span><span></span></div>
        </div>
      </div>

      <!-- Error -->
      <div v-if="chat.error" class="error-banner">
        <span>{{ chat.error }}</span>
        <button @click="chat.error = null">x</button>
      </div>
    </div>

    <!-- Scroll to bottom bar -->
    <Transition name="fade">
      <button v-if="showScrollBtn" class="scroll-bar" @click="scrollToBottom(true)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="6 9 12 15 18 9"/></svg>
        回到最新
      </button>
    </Transition>

    <!-- Image Preview -->
    <Transition name="fade">
      <div v-if="imagePreview" class="image-preview-bar">
        <img :src="imagePreview" class="preview-thumb" />
        <span class="preview-name">{{ imageName }}</span>
        <button class="preview-remove" @click="clearImage">x</button>
      </div>
    </Transition>

    <!-- Input -->
    <div class="input-bar" :class="{ focused: inputFocused }">
      <div class="input-row">
        <label class="attach-btn" for="img-upload">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
          <input id="img-upload" type="file" accept="image/*" @change="onImageSelect" hidden />
        </label>
        <textarea
          ref="inputRef"
          class="input-field"
          v-model="inputText"
          placeholder="输入消息..."
          @keydown.enter.exact.prevent="send"
          @focus="inputFocused = true"
          @blur="inputFocused = false"
          @input="autoResize"
          rows="1"
        ></textarea>
        <button v-if="inputText.trim() || imageFile" class="send-btn" @click="send" :disabled="chat.isStreaming">
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
        </button>
        <button v-else class="send-btn voice-btn" @click="toggleVoice" :class="{ recording: isRecording }">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
        </button>
      </div>
    </div>

    <!-- Action Sheet -->
    <Transition name="sheet">
      <div v-if="actionSheet.show" class="action-sheet-overlay" @click.self="actionSheet.show = false">
        <div class="action-sheet">
          <div class="action-sheet-title">{{ actionSheet.msg?.role === 'user' ? userName : aiName }}</div>
          <button class="action-item" @click="doCopy">复制</button>
          <button v-if="actionSheet.msg?.role === 'user'" class="action-item" @click="startEdit">编辑</button>
          <button class="action-item" @click="doFavorite">
            {{ chat.favoriteIds.has(actionSheet.msg?.id) ? '取消收藏' : '收藏' }}
          </button>
          <button v-if="actionSheet.msg?.role === 'assistant' && isLastMsg" class="action-item" @click="doReroll">重新生成</button>
          <button v-if="actionSheet.msg?.id" class="action-item danger" @click="doDelete">删除</button>
          <button class="action-item cancel" @click="actionSheet.show = false">取消</button>
        </div>
      </div>
    </Transition>

    <!-- Edit Sheet -->
    <Transition name="sheet">
      <div v-if="editSheet.show" class="action-sheet-overlay" @click.self="cancelEdit">
        <div class="action-sheet" @click.stop>
          <div class="action-sheet-title">编辑消息</div>
          <div class="edit-body">
            <textarea class="input-area-field edit-input" v-model="editSheet.text" rows="3" ref="editRef"></textarea>
          </div>
          <div class="sheet-btns">
            <button class="cancel-btn" @click="cancelEdit">取消</button>
            <button class="primary-btn" @click="confirmEdit">确认</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useChatStore } from '../stores/chatStore.js'
import { useAppStore } from '../stores/appStore.js'

const chat = useChatStore()
const app = useAppStore()

const inputText = ref('')
const listRef = ref(null)
const inputRef = ref(null)
const actionSheet = ref({ show: false, msg: null })
const editSheet = ref({ show: false, msg: null, text: '' })
const inputFocused = ref(false)
const showScrollBtn = ref(false)
const pullDistance = ref(0)
const isRecording = ref(false)
const newMsgCount = ref(0)
const imageFile = ref(null)
const imagePreview = ref('')
const imageName = ref('')
const showCmdInput = ref(false)
const cmdText = ref('')
const cmdRef = ref(null)

const messages = computed(() => chat.messages)
const aiName = computed(() => app.charName)
const userName = computed(() => app.userName)
const avatarUrl = computed(() => app.avatarUrl)
const charDesc = computed(() => app.activeCharacter?.description?.slice(0, 50) || '')
const quickPhrases = ['你好', '讲个故事', '今天过得怎么样']
const cmdHints = [
  { cmd: '/help', desc: '帮助' },
  { cmd: '/reroll', desc: '重新生成' },
  { cmd: '/reset', desc: '重置对话' },
  { cmd: '/export', desc: '导出记录' },
]
const isLastMsg = computed(() => {
  const msg = actionSheet.value.msg
  if (!msg) return false
  return chat.lastAssistantMsg?.id === msg.id || chat.lastAssistantMsg?.content === msg.content
})

async function send() {
  if (chat.isStreaming) return
  const text = inputText.value.trim()
  const hasImage = !!imageFile.value
  if (!text && !hasImage) return

  // If image, upload first
  if (hasImage) {
    app.showToast('上传图片中...')
    const b64 = await uploadImage()
    if (b64) {
      // Send image message
      chat.sendMessage(`[图片]\n${text || ''}`, b64)
    } else {
      app.showToast('图片上传失败')
      return
    }
    clearImage()
  } else {
    chat.sendMessage(text)
  }
  inputText.value = ''
  if (inputRef.value) inputRef.value.style.height = 'auto'
  nextTick(() => scrollToBottom(true))
}

function sendQuick(q) {
  chat.sendMessage(q)
  nextTick(() => scrollToBottom(true))
}

function execCmd() {
  const cmd = cmdText.value.trim()
  if (!cmd) return
  chat.sendMessage(cmd)
  showCmdInput.value = false
  cmdText.value = ''
  nextTick(() => scrollToBottom(true))
}

function execCmdDirect(cmd) {
  chat.sendMessage(cmd)
  showCmdInput.value = false
  nextTick(() => scrollToBottom(true))
}

function autoResize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function scrollToBottom(smooth = false) {
  if (!listRef.value) return
  if (smooth) {
    listRef.value.scrollTo({ top: listRef.value.scrollHeight, behavior: 'smooth' })
  } else {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
}

function onScroll() {
  if (!listRef.value) return
  const { scrollTop, scrollHeight, clientHeight } = listRef.value
  showScrollBtn.value = scrollHeight - scrollTop - clientHeight > 150
}

let _touchStartY = 0
function onTouchStart(e) {
  _touchStartY = e.touches[0].clientY
}

function onTouchEnd(e) {
  const dy = e.changedTouches[0].clientY - _touchStartY
  if (dy > 80 && listRef.value && listRef.value.scrollTop < 10) {
    chat.loadHistory()
  }
  pullDistance.value = 0
}

function isNewMsg(idx) {
  return idx >= messages.value.length - newMsgCount.value
}

function showDateSep(msg, idx) {
  if (!msg.timestamp) return false
  if (idx === 0) return true
  const prev = messages.value[idx - 1]
  return msg.timestamp.slice(0, 10) !== (prev?.timestamp || '').slice(0, 10)
}

function formatDate(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const today = new Date()
  if (d.toDateString() === today.toDateString()) return '今天'
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  if (d.toDateString() === yesterday.toDateString()) return '昨天'
  return `${d.getMonth() + 1}月${d.getDate()}日`
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

function onMsgTap(e, msg) {
  actionSheet.value = { show: true, msg }
}

function doCopy() {
  navigator.clipboard.writeText(actionSheet.value.msg?.content || '')
  app.showToast('已复制')
  actionSheet.value.show = false
}

function doFavorite() {
  if (actionSheet.value.msg) chat.toggleFavorite(actionSheet.value.msg)
  actionSheet.value.show = false
}

function doReroll() {
  chat.reroll()
  actionSheet.value.show = false
}

function doDelete() {
  if (actionSheet.value.msg) chat.deleteMessage(actionSheet.value.msg)
  actionSheet.value.show = false
}

function startEdit() {
  const msg = actionSheet.value.msg
  if (!msg) return
  editSheet.value = { show: true, msg, text: msg.content || '' }
  actionSheet.value.show = false
  nextTick(() => { document.querySelector('.edit-input')?.focus() })
}

function cancelEdit() {
  editSheet.value.show = false
  editSheet.value.msg = null
}

function confirmEdit() {
  const text = editSheet.value.text.trim()
  const msg = editSheet.value.msg
  editSheet.value.show = false
  editSheet.value.msg = null
  if (!text || !msg) return

  // Send edit via WebSocket
  if (chat.ws && chat.ws.readyState === 1) {
    chat.ws.send(JSON.stringify({
      type: 'edit',
      msg_id: msg.id,
      message: text,
    }))
  }
}

function onImageSelect(e) {
  const file = e.target.files[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    app.showToast('图片不能超过 10MB')
    return
  }
  imageFile.value = file
  imageName.value = file.name
  const reader = new FileReader()
  reader.onload = (ev) => { imagePreview.value = ev.target.result }
  reader.readAsDataURL(file)
}

function clearImage() {
  imageFile.value = null
  imagePreview.value = ''
  imageName.value = ''
}

async function uploadImage() {
  if (!imageFile.value) return null
  const form = new FormData()
  form.append('file', imageFile.value)
  try {
    const res = await api.post('/vision/upload', form)
    return res.data?.base64 || null
  } catch {
    return null
  }
}

function toggleVoice() {
  isRecording.value = !isRecording.value
  if (!isRecording.value) {
    app.showToast('语音输入功能开发中')
  }
}

function onOpenCmd() {
  showCmdInput.value = true
  nextTick(() => { cmdRef.value?.focus() })
}

onMounted(() => {
  window.addEventListener('open-cmd', onOpenCmd)
  watch(() => chat.messages.length, (newLen, oldLen) => {
    newMsgCount.value = newLen - (oldLen || 0)
    nextTick(() => {
      scrollToBottom()
      setTimeout(() => { newMsgCount.value = 0 }, 500)
    })
  })
  watch(() => chat.pendingReply, () => {
    if (!showScrollBtn.value) nextTick(scrollToBottom)
  }, { deep: true })
  nextTick(scrollToBottom)
})

onUnmounted(() => {
  window.removeEventListener('open-cmd', onOpenCmd)
})
</script>
