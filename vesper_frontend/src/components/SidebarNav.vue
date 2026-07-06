<script setup>
import { useChat } from '../stores/chatStore.js'

defineProps({ current: String })
const emit = defineEmits(['navigate'])
const chat = useChat()

const items = [
  { id: 'chat', label: '对话', icon: '💬' },
  { id: 'characters', label: '角色', icon: '🎭' },
  { id: 'settings', label: '设置', icon: '⚙️' },
]
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-icon">●</span>
      <span class="brand-name">夕语</span>
    </div>

    <nav class="nav">
      <button
        v-for="item in items"
        :key="item.id"
        class="nav-item"
        :class="{ active: current === item.id }"
        @click="emit('navigate', item.id)"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <div class="status">
      <span class="status-dot" :class="{ online: chat.connected }"></span>
      <span class="status-label">{{ chat.connected ? '已连接' : '离线' }}</span>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  height: 100%;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.brand {
  padding: 16px 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--border);
}
.brand-icon {
  font-size: 10px;
  color: var(--primary);
}
.brand-name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.3px;
}
.nav {
  flex: 1;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: var(--radius-md);
  border: none;
  background: none;
  color: var(--text-muted);
  font-family: var(--font-sans);
  font-size: 13.5px;
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
  width: 100%;
}
.nav-item:hover { background: var(--bg-hover); color: var(--text); }
.nav-item.active {
  background: var(--primary-muted);
  color: var(--primary);
}
.nav-icon { font-size: 15px; }
.status {
  padding: 12px 18px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-tertiary);
}
.status-dot.online { background: var(--success); }
.status-label { font-size: 12px; color: var(--text-muted); }
</style>
