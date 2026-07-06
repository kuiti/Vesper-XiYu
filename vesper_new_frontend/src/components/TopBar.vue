<template>
  <div class="top-bar">
    <span class="accent">{{ charName }}</span>
    <span class="sep">/</span>
    <span>{{ chat.totalMessages }} messages</span>
    <span class="sep">/</span>
    <span :class="chat.wsReady ? 'green' : ''">{{ chat.wsReady ? 'connected' : 'disconnected' }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useChatStore } from '../stores/chatStore.js'
import { useAppStore } from '../stores/appStore.js'

const chat = useChatStore()
const app = useAppStore()
const charName = computed(() => app.activeCharacter?.name || 'default')
</script>
