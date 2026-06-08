<template>
  <ChatView
    :ws="chatStore.wsRaw"
    :wsReady="chatStore.wsReady"
    :messages="chatStore.messages"
    :isStreaming="chatStore.isStreaming"
    :pendingReply="streamText"
    :aiNameLocal="settingsStore.aiName"
    :userNameLocal="settingsStore.userName"
    :assistantAvatarUrl="avatarUrl"
    :userAvatarUrl="userAvatarUrl"
    :quickPhrases="quickPhrases"
    :favoriteIds="chatStore.favoriteIds"
    :sentenceMode="sentenceMode"
    :quickReplies="quickReplies"
    :todayLearning="todayLearning"
    :timelineDates="timelineDates"
    :nextAfterId="chatStore.nextAfterId"
    :loadingMore="chatStore.loadingMore"
    :floatingDate="floatingDate"
    :ipCity="ipCity"
    :ipCityShort="ipCityShort"
    :totalMessages="chatStore.totalMessages"
    :reminderCount="reminderCount"
    :chatFontSize="chatFontSize"
    :kaomojis="kaomojis"
    :historyReady="chatStore.historyReady"
    :voiceSettings="voiceSettings"
    @send="onSend"
    @toggle-favorite="chatStore.toggleFavorite"
    @context-menu-action="onCtxAction"
    @load-more="chatStore.loadMoreHistory"
    @delete-message="onDelete"
    @clear-today-learning="todayLearning = null"
    @feedback="onFeedback"
  />
</template>

<script>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useChatStore } from '../stores/chat.js'
import { useSettingsStore } from '../stores/settings.js'
import { useUiStore } from '../stores/ui.js'
import api from '../api.js'
import ChatView from '../components/ChatView.vue'

export default {
  components: { ChatView },
  setup() {
    const chatStore = useChatStore()
    const settingsStore = useSettingsStore()
    const ui = useUiStore()

    const streamText = ref('')
    const todayLearning = ref(null)
    const timelineDates = ref([])
    const quickPhrases = ref([])
    const quickReplies = ref(['展开说说', '换个角度', '好的', '继续'])
    const sentenceMode = ref('auto')
    const ipCity = ref('')
    const ipCityShort = ref('')
    const reminderCount = ref(0)
    const chatFontSize = ref(14)
    const floatingDate = ref('')
    const avatarUrl = ref('')
    const userAvatarUrl = ref('')
    const kaomojis = ref(['(・ω・)','(´∀｀)','(╯°□°)╯','( ；∀；)','(￣▽￣)','(⌒▽⌒)','（＾ω＾）','(・∀・)','(｀・ω・´)','(＞＜)','(T_T)','(^_^;)','( ´ ▽ ` )','(・へ・)','(≧∇≦)','(-_-;)','(￣ε￣)','(・_・;)','(゜∀゜)','(；一_一)','( ´ー｀)','(´・ω・｀)','(Θ_Θ)','(。-ω-)zzz','ヽ(・∀・)ノ'])
    const voiceSettings = reactive({
      tts_enabled: false, tts_engine: 'off', auto_play: false, tts_clone_audio: false, tts_clone_mode: ''
    })

    let _streamTimeout = null
    let _isSystemStreaming = false

    function onWsMessage(event) {
      let data
      try { data = JSON.parse(event.data) } catch (e) { return }
      if (data.type === 'token') {
        if (_isSystemStreaming) return
        if (streamText.value.length < 50000) streamText.value += data.content
      } else if (data.type === 'done') {
        if (data._system) { _isSystemStreaming = false; streamText.value = ''; chatStore.isStreaming = false; return }
        chatStore.isStreaming = false
        clearTimeout(_streamTimeout)
      } else if (data.type === 'greeting') {
        const msgs = chatStore.messages
        const last = msgs[msgs.length - 1]
        if (!last || (last.role === 'assistant' && !last.isProactive && !last._isGreeting) || last.role === 'user') {
          msgs.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString(), _isGreeting: true })
          chatStore.totalMessages++
        }
      } else if (data.type === 'proactive') {
        const last2 = chatStore.messages.slice(-2)
        const hasProactive = last2.some(m => m.role === 'assistant' && m.isProactive)
        if (!hasProactive) {
          chatStore.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString(), isProactive: true })
          chatStore.totalMessages++
        }
      } else if (data.type === 'weather') {
        chatStore.messages.push({ role: 'assistant', content: '__WEATHER_CARD__', weatherData: data.data, timestamp: new Date().toISOString(), isWeather: true })
        chatStore.totalMessages++
      } else if (data.type === 'reroll_start') {
        streamText.value = ''
        chatStore.isStreaming = true
      } else if (data.type === 'surprise') {
        chatStore.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString(), isSurprise: true })
        chatStore.totalMessages++
      } else if (data.type === 'reminder') {
        const rText = data.data?.content || data.data?.title || ''
        ui.notify({ type: 'info', content: '⏰ 提醒: ' + rText, duration: 8000 })
        reminderCount.value = Math.max(0, reminderCount.value)
      } else if (data.type === 'reminder_count') {
        reminderCount.value = data.count || 0
      } else if (data.type === 'achievement') {
        ui.notify({ type: 'success', content: '🏆 ' + (data.data?.name || '成就达成') })
      } else if (data.type === 'toast') {
        ui.notify({ type: 'info', content: data.content, duration: Math.min(10000, Math.max(3000, (data.content || '').length * 80)) })
      } else if (data.type === 'dsml_tool_call') {
        streamText.value = ''
        chatStore.isStreaming = false
        const last = chatStore.messages[chatStore.messages.length - 1]
        if (last && last.role === 'assistant' && last.content && last.content.includes('DSML')) {
          chatStore.messages.pop()
          chatStore.totalMessages--
        }
      } else if (data.type === 'error') {
        chatStore.messages.push({ role: 'assistant', content: '错误：' + data.content, timestamp: new Date().toISOString() })
        chatStore.isStreaming = false
      }
    }

    function onSend(msg) {
      if (!msg || chatStore.isStreaming) return
      const now = new Date()
      chatStore.messages.push({ role: 'user', content: msg, timestamp: now.toISOString() })
      chatStore.totalMessages++
      chatStore.isStreaming = true
      streamText.value = ''
      chatStore.send({
        message: msg,
        history: chatStore.messages
          .filter(m => !m._sentenceFrag && !m.isWeather && !m._isGreeting && !m.isProactive && !m.isSurprise)
          .slice(0, -1).slice(-35)
          .map(m => ({ role: m.role, content: m.content, timestamp: m.timestamp }))
      })
      clearTimeout(_streamTimeout)
      _streamTimeout = setTimeout(() => {
        if (chatStore.isStreaming) {
          chatStore.isStreaming = false
          if (streamText.value) {
            chatStore.messages.push({ role: 'assistant', content: streamText.value + '\n(回复被中断)', timestamp: new Date().toISOString() })
            streamText.value = ''
          }
        }
      }, 60000)
    }

    function onCtxAction(action, msg) {
      if (action === 'toggle-favorite') chatStore.toggleFavorite(msg)
      else if (action === 'reroll-from' && msg?.id && chatStore.wsReady) {
        const idx = chatStore.messages.findIndex(m => m.id === msg.id)
        if (idx !== -1) { chatStore.messages = chatStore.messages.slice(0, idx); chatStore.totalMessages = chatStore.messages.length }
        chatStore.isStreaming = true; streamText.value = ''
        chatStore.send({ message: `/reroll_from:${msg.id}`, history: chatStore.messages.slice(-35).map(m => ({ role: m.role, content: m.content })) })
      }
    }

    function onDelete(msgId) {
      chatStore.messages = chatStore.messages.filter(m => m.id !== msgId)
      chatStore.totalMessages = chatStore.messages.length
    }

    function onFeedback({ msgId, score }) {
      if (chatStore.wsReady) {
        chatStore.send({ type: 'feedback', msg_id: msgId, score })
      }
    }

    // Load auxiliary data
    onMounted(async () => {
      chatStore.loadHistory()
      chatStore.loadFavoriteIds()
      chatStore.connect(onWsMessage)

      try {
        const s = settingsStore.allSettings
        if (s.quick_phrases) quickPhrases.value = typeof s.quick_phrases === 'string' ? JSON.parse(s.quick_phrases) : s.quick_phrases
        if (s.sentence_mode) sentenceMode.value = s.sentence_mode
        if (s.chat_font_size) chatFontSize.value = Number(s.chat_font_size)
        if (s.precise_city) { ipCity.value = s.precise_city; const parts = s.precise_city.split('·'); ipCityShort.value = parts[parts.length - 1] || s.precise_city }
        // Voice settings
        const v = settingsStore.allSettings
        voiceSettings.tts_enabled = v.tts_enabled
        voiceSettings.tts_engine = v.tts_engine
        voiceSettings.auto_play = v.auto_play_voice
        voiceSettings.tts_clone_audio = v.tts_clone_audio
        voiceSettings.tts_clone_mode = v.tts_clone_mode
      } catch (e) {}

      try { const res = await api.get('/avatar/assistant'); if (res.data?.url) avatarUrl.value = res.data.url } catch (e) {}
      try { const res = await api.get('/avatar/user'); if (res.data?.url) userAvatarUrl.value = res.data.url } catch (e) {}
      try { const res = await api.get('/memory/today-learning'); if (res.data?.has_new) todayLearning.value = res.data } catch (e) {}
      try { const res = await api.get('/chat/history/dates'); const months = res.data?.months || []; timelineDates.value = months.flatMap(m => (m.dates || []).map(d => d.date)) } catch (e) {}
      try { const res = await api.get('/location/ip'); if (res.data?.city) { ipCity.value = res.data.city; ipCityShort.value = res.data.city } } catch (e) {}
    })

    onBeforeUnmount(() => {
      chatStore.disconnect()
      clearTimeout(_streamTimeout)
    })

    return {
      chatStore, settingsStore, streamText,
      todayLearning, timelineDates, quickPhrases, quickReplies,
      sentenceMode, ipCity, ipCityShort, reminderCount, chatFontSize,
      floatingDate, avatarUrl, userAvatarUrl, kaomojis, voiceSettings,
      onSend, onCtxAction, onDelete, onFeedback,
    }
  },
}
</script>
