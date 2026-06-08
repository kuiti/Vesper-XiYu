<template>
  <div class="tools-page">
    <KnowledgePanel :aiName="settingsStore.aiName" />
    <RAGPanel />
    <GoalPanel :aiName="settingsStore.aiName" />
    <HabitTracker />
    <NoteList />
    <CountdownList />
    <ReminderList />
    <ChatManagePanel />
  </div>
</template>

<script>
import { useSettingsStore } from '../stores/settings.js'
import KnowledgePanel from '../components/KnowledgePanel.vue'
import RAGPanel from '../components/RAGPanel.vue'
import GoalPanel from '../components/GoalPanel.vue'
import HabitTracker from '../components/HabitTracker.vue'
import NoteList from '../components/NoteList.vue'
import CountdownList from '../components/CountdownList.vue'
import ReminderList from '../components/ReminderList.vue'
import ChatManagePanel from '../components/ChatManagePanel.vue'

export default {
  components: { KnowledgePanel, RAGPanel, GoalPanel, HabitTracker, NoteList, CountdownList, ReminderList, ChatManagePanel },
  setup() {
    const settingsStore = useSettingsStore()
    return { settingsStore }
  },
}
</script>
<style scoped>
.tools-page { padding: 16px; overflow-y: auto; height: 100%; display: flex; flex-direction: column; gap: 16px; }
</style>
