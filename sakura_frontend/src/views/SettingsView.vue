<template>
  <SettingsView
    :settings="settingsStore.allSettings"
    themeLocal="dark"
    :ipCity="globalStore.ipCity"
    :relationship="globalStore.relationship"
    :emotionTrend="globalStore.emotionTrend"
    :totalMessages="messages.length"
    :conversationDays="globalStore.conversationDays"
    :assistantAvatarUrl="globalStore.assistantAvatarUrl"
    :userAvatarUrl="globalStore.userAvatarUrl"
    @config-changed="onConfigChanged"
    @export-chat="exportChat"
    @close="router.push({name:'chat'})"
  />
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSettingsStore } from '../stores/settings.js'
import { useGlobalStore } from '../stores/global.js'
import { useChatStore } from '../stores/chat.js'
import api from '../api.js'
import { alert as showAlert } from '../utils/dialog.js'
import SettingsView from '../components/SettingsView.vue'

export default {
  components: { SettingsView },
  setup() {
    const router = useRouter()
    const settingsStore = useSettingsStore()
    const globalStore = useGlobalStore()
    const chatStore = useChatStore()
    const messages = ref(chatStore.messages)

    onMounted(() => { globalStore.loadAll() })

    function onConfigChanged(key, value) {
      settingsStore.update(key, value)
      api.post('/settings/', { key, value }).catch(() => {})
    }

    async function exportChat(fmt) {
      const format = fmt || 'txt'
      try {
        const res = await api.get(`/export/chat?format=${format}`)
        const blob = new Blob([res.data.content], { type: format === 'md' ? 'text/markdown' : 'text/plain' })
        const url = URL.createObjectURL(blob); const a = document.createElement('a')
        a.href = url; a.download = res.data.filename; a.click(); URL.revokeObjectURL(url)
      } catch (e) { showAlert('导出失败') }
    }

    return { settingsStore, globalStore, messages, router, onConfigChanged, exportChat }
  },
}
</script>
