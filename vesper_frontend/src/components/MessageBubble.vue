<script setup>
defineProps({ msg: Object, index: Number })
</script>

<template>
  <div class="row" :class="msg.role" :style="{ animationDelay: (index || 0) * 30 + 'ms' }">
    <div v-if="msg.role === 'assistant'" class="av">A</div>
    <div class="wrap">
      <div v-if="msg.sender" class="sender">{{ msg.sender }}</div>
      <div class="bubble" :class="{ streaming: msg.streaming }">
        <span class="text">{{ msg.content }}</span>
        <span v-if="msg.streaming" class="cur"></span>
      </div>
    </div>
    <div v-if="msg.role === 'user'" class="av user-av">U</div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  gap: 8px;
  max-width: 78%;
  margin-bottom: 4px;
  animation: msgUp 0.25s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes msgUp {
  from { opacity: 0; transform: translateY(8px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.row.user { margin-left: auto; flex-direction: row-reverse; }

.av {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-muted);
  flex-shrink: 0;
  margin-top: 4px;
  border: 1px solid var(--border);
}
.user-av { background: var(--bg-active); color: var(--accent); }

.wrap { display: flex; flex-direction: column; gap: 2px; }
.sender { font-size: 11px; color: var(--text-muted); padding-left: 4px; font-weight: 500; }

.bubble {
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.55;
  word-break: break-word;
  white-space: pre-wrap;
  position: relative;
}
.assistant .bubble {
  background: var(--msg-ai-bg);
  border: 1px solid var(--border);
  border-top-left-radius: 4px;
  border-top-right-radius: var(--radius-lg);
  border-bottom-right-radius: var(--radius-lg);
  border-bottom-left-radius: var(--radius-lg);
}
.user .bubble {
  background: var(--msg-user-bg);
  border: none;
  border-top-left-radius: var(--radius-lg);
  border-top-right-radius: 4px;
  border-bottom-right-radius: var(--radius-lg);
  border-bottom-left-radius: var(--radius-lg);
}
.user .bubble::after {
  content: '';
  position: absolute;
  top: 10px; right: -4px;
  width: 8px; height: 8px;
  background: var(--accent-end);
  clip-path: polygon(0 0, 100% 50%, 0 100%);
}

.text { color: inherit; }
.user .text { color: white; }

.cur {
  display: inline-block;
  width: 2px;
  height: 14px;
  background: white;
  animation: blink 0.8s infinite;
  vertical-align: text-bottom;
  margin-left: 1px;
}
@keyframes blink { 50% { opacity: 0; } }
</style>
