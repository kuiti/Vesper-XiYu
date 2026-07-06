<template>
  <div class="app-root">
    <div class="ambient-bg"></div>

    <!-- Sidebar -->
    <nav class="sidebar">
      <span class="sidebar-brand">夕语</span>
      <button :class="['nav-btn', { active: view === 'chat' }]" @click="go('chat')" title="Chat">C</button>
      <button :class="['nav-btn', { active: view === 'characters' }]" @click="go('characters')" title="Characters">R</button>
      <button :class="['nav-btn', { active: view === 'settings' }]" @click="go('settings')" title="Settings">S</button>
      <button :class="['nav-btn', { active: view === 'memory' }]" @click="go('memory')" title="Memory">M</button>
      <span class="sidebar-spacer"></span>
      <button class="nav-btn" @click="app.toggleCmdPalette()" title="Command Palette">/</button>
    </nav>

    <!-- Main -->
    <main class="main-area">
      <TopBar />
      <ChatView v-if="view === 'chat'" />
      <CharactersView v-else-if="view === 'characters'" />
      <SettingsView v-else-if="view === 'settings'" />
      <MemoryView v-else-if="view === 'memory'" />
    </main>

    <!-- Command Palette -->
    <CommandPalette v-if="app.showCmdPalette" @close="app.showCmdPalette = false" @select="handleCmd" />

    <!-- Toast -->
    <div v-if="app.toast" class="toast">{{ app.toast }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from './stores/appStore.js'
import { useChatStore } from './stores/chatStore.js'
import TopBar from './components/TopBar.vue'
import ChatView from './components/ChatView.vue'
import CharactersView from './components/CharactersView.vue'
import SettingsView from './components/SettingsView.vue'
import MemoryView from './components/MemoryView.vue'
import CommandPalette from './components/CommandPalette.vue'

const app = useAppStore()
const chat = useChatStore()
const view = ref('chat')

function go(v) {
  view.value = v
}

function handleCmd(cmd) {
  if (cmd === 'chat') { view.value = 'chat' }
  else if (cmd === 'characters') { view.value = 'characters' }
  else if (cmd === 'settings') { view.value = 'settings' }
  else if (cmd === 'memory') { view.value = 'memory' }
}

onMounted(() => {
  app.loadSettings()
  app.loadActiveCharacter()
  chat.connectWebSocket()
  chat.loadHistory()
  chat.loadFavorites()

  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault()
      app.toggleCmdPalette()
    }
  })
})
</script>
