<template>
  <DiaryPanel :aiName="settingsStore.aiName" />
</template>

<script>
import { useSettingsStore } from '../stores/settings.js'
import DiaryPanel from '../components/DiaryPanel.vue'

export default {
  components: { DiaryPanel },
  setup() {
    const settingsStore = useSettingsStore()
    return { settingsStore }
  },
}
</script>
