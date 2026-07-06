<template>
  <!-- Setup Screen -->
  <SetupView v-if="showSetup" @connect="onConnect" />

  <!-- Main App -->
  <div v-else class="app-root" :class="{ 'keyboard-open': keyboardOpen }">
    <div class="ambient-bg"></div>

    <!-- Status Bar -->
    <header class="status-bar" @dblclick="openCmd">
      <span class="status-name">{{ app.charName }}</span>
      <span class="status-dot" :class="chat.wsReady ? 'online' : 'offline'"></span>
      <span class="status-label">{{ chat.wsReady ? 'online' : 'offline' }}</span>
      <span class="status-spacer"></span>
      <span class="status-count">{{ chat.totalMessages }} msgs</span>
    </header>

    <!-- Page Content -->
    <main class="page-content">
      <Transition :name="transitionName" mode="out-in">
        <ChatView v-if="app.currentTab === 'chat'" key="chat" />
        <CharactersView v-else-if="app.currentTab === 'characters'" key="characters" />
        <SettingsView v-else-if="app.currentTab === 'settings'" key="settings" />
        <MemoryView v-else-if="app.currentTab === 'memory'" key="memory" />
      </Transition>
    </main>

    <!-- Bottom Navigation -->
    <nav class="bottom-nav">
      <button :class="['nav-item', { active: app.currentTab === 'chat' }]" @click="switchTab('chat')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
        <span>Chat</span>
      </button>
      <button :class="['nav-item', { active: app.currentTab === 'characters' }]" @click="switchTab('characters')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4-4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
        <span>角色</span>
      </button>
      <button :class="['nav-item', { active: app.currentTab === 'memory' }]" @click="switchTab('memory')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        <span>记忆</span>
      </button>
      <button :class="['nav-item', { active: app.currentTab === 'settings' }]" @click="switchTab('settings')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.32 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
        <span>设置</span>
      </button>
    </nav>

    <!-- Toast -->
    <Transition name="toast">
      <div v-if="app.toast" class="toast">{{ app.toast }}</div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAppStore } from './stores/appStore.js'
import { useChatStore } from './stores/chatStore.js'
import SetupView from './components/SetupView.vue'
import ChatView from './components/ChatView.vue'
import CharactersView from './components/CharactersView.vue'
import SettingsView from './components/SettingsView.vue'
import MemoryView from './components/MemoryView.vue'

const app = useAppStore()
const chat = useChatStore()
const keyboardOpen = ref(false)
const transitionName = ref('fade')
const prevTab = ref('chat')
const showSetup = ref(!localStorage.getItem('vesper_host'))

const tabOrder = ['chat', 'characters', 'memory', 'settings']

function switchTab(tab) {
  const prevIdx = tabOrder.indexOf(prevTab.value)
  const nextIdx = tabOrder.indexOf(tab)
  transitionName.value = nextIdx > prevIdx ? 'slide-left' : 'slide-right'
  prevTab.value = tab
  app.currentTab = tab
}

function onResize() {
  const vh = window.visualViewport?.height || window.innerHeight
  keyboardOpen.value = vh < window.innerHeight * 0.75
}

function onConnect() {
  showSetup.value = false
  initApp()
}

function openCmd() {
  // Trigger command input in ChatView
  const event = new CustomEvent('open-cmd')
  window.dispatchEvent(event)
}

function initApp() {
  app.loadSettings()
  app.loadActiveCharacter()
  chat.connectWebSocket()
  chat.loadHistory()
  chat.loadFavorites()
}

onMounted(() => {
  if (!showSetup.value) {
    initApp()
  }
  window.visualViewport?.addEventListener('resize', onResize)
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.visualViewport?.removeEventListener('resize', onResize)
  window.removeEventListener('resize', onResize)
})
</script>
