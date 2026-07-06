<template>
  <div class="cmd-palette" @click.self="$emit('close')">
    <div class="cmd-box">
      <input ref="inputRef" class="cmd-input" v-model="query" placeholder="Type a command..." @keydown.escape="$emit('close')" @keydown.enter="selectCurrent" @keydown.up.prevent="move(-1)" @keydown.down.prevent="move(1)" autofocus />
      <div class="cmd-list">
        <div v-for="(cmd, i) in filtered" :key="cmd.id" :class="['cmd-item', { selected: i === selected }]" @click="$emit('select', cmd.id); $emit('close')">
          <span class="cmd-item-icon">{{ cmd.icon }}</span>
          <span class="cmd-item-label">{{ cmd.label }}</span>
          <span class="cmd-item-hint">{{ cmd.hint }}</span>
        </div>
        <div v-if="!filtered.length" style="padding: 16px 20px; color: var(--text-muted); font-size: 13px;">No matches</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const emit = defineEmits(['close', 'select'])
const query = ref('')
const selected = ref(0)

const commands = [
  { id: 'chat', icon: 'C', label: 'Chat', hint: 'Go to chat' },
  { id: 'characters', icon: 'R', label: 'Characters', hint: 'Manage characters' },
  { id: 'settings', icon: 'S', label: 'Settings', hint: 'App settings' },
  { id: 'memory', icon: 'M', label: 'Memory', hint: 'View memory' },
]

const filtered = computed(() => {
  if (!query.value) return commands
  const q = query.value.toLowerCase()
  return commands.filter(c => c.label.toLowerCase().includes(q) || c.hint.toLowerCase().includes(q))
})

function move(d) {
  selected.value = Math.max(0, Math.min(filtered.value.length - 1, selected.value + d))
}

function selectCurrent() {
  if (filtered.value[selected.value]) {
    emit('select', filtered.value[selected.value].id)
    emit('close')
  }
}
</script>
