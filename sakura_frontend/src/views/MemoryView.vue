<template>
  <div class="memory-page">
    <MemoryPanel :aiName="settingsStore.aiName" />
    <MemoryVault />
  </div>
</template>

<script>
import { onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings.js'
import MemoryPanel from '../components/MemoryPanel.vue'
import MemoryVault from '../components/MemoryVault.vue'

export default {
  components: { MemoryPanel, MemoryVault },
  setup() {
    const settingsStore = useSettingsStore()
    return { settingsStore }
  },
}
</script>
<style scoped>
.memory-page { padding: 16px; overflow-y: auto; height: 100%; }
</style>
