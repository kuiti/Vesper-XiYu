<script setup>
import { onMounted, onUnmounted } from 'vue'
import { connect, disconnect, useChat } from './stores/chatStore.js'
import { fetchCharacters } from './utils/api.js'
import ContactSidebar from './components/ContactSidebar.vue'

const chat = useChat()
onMounted(async () => {
  try { chat.characters = (await fetchCharacters()).characters || [] } catch (_) {}
  connect()
})
onUnmounted(() => disconnect())
</script>

<template>
  <div class="shell">
    <div class="ambient-bg"></div>
    <div class="app">
      <ContactSidebar />
      <main class="stage">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell { height: 100%; position: relative; overflow: hidden; }
.ambient-bg {
  position: fixed; inset: 0; z-index: 0;
  background:
    radial-gradient(ellipse 600px 400px at 10% 30%, rgba(114,137,254,0.04) 0%, transparent 70%),
    radial-gradient(ellipse 500px 500px at 90% 70%, rgba(155,123,253,0.03) 0%, transparent 70%);
  pointer-events: none;
}
.app { position: relative; z-index: 1; display: flex; height: 100%; max-width: 1440px; margin: 0 auto; }
.stage { flex: 1; display: flex; flex-direction: column; min-width: 0; background: var(--bg-chat); position: relative; border-left: 1px solid var(--border); }
</style>
