<template>
  <HistoryView
    :favoriteIds="chatStore.favoriteIds"
    :aiName="settingsStore.aiName"
    :userName="settingsStore.userName"
    @close="router.push({name:'chat'})"
    @toggle-favorite="chatStore.toggleFavorite"
  />
</template>

<script>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat.js'
import { useSettingsStore } from '../stores/settings.js'
import HistoryView from '../components/HistoryView.vue'

export default {
  components: { HistoryView },
  setup() {
    const router = useRouter()
    const chatStore = useChatStore()
    const settingsStore = useSettingsStore()
    onMounted(() => { chatStore.loadFavoriteIds() })
    return { router, chatStore, settingsStore }
  },
}
</script>
