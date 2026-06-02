<template>
  <div class="chat-input-area">
    <div v-if="quickPhrases.length" class="quick-bar">
      <span v-for="(p, i) in quickPhrases" :key="i" class="qp-chip" @click="$emit('send', p)">{{ p }}</span>
    </div>
    <div v-if="quoteMsg" class="quote-bar">
      <span class="quote-preview">{{ quoteMsg.content?.slice(0, 60) }}...</span>
      <button class="quote-close" @click="$emit('clear-quote')">x</button>
    </div>
    <div class="input-row">
      <button class="emoji-btn" @click="showEmoji = !showEmoji" title="颜文字">^_^</button>
      <div v-if="showEmoji" class="emoji-picker">
        <span v-for="k in kaomojis" :key="k" class="emoji-item" @click="insertEmoji(k)">{{ k }}</span>
      </div>
      <textarea ref="el" v-model="text" @keydown.enter.exact.prevent="send" @keydown.shift.enter="newline" @input="resize"
        :placeholder="placeholderText" rows="1" class="chat-input"
      ></textarea>
      <button class="send-btn" @click="send" :disabled="!text.trim()">发送</button>
    </div>
    <div class="input-hint">Enter 发送 · Shift+Enter 换行 · End 回到底部 · Ctrl+1-5 切换视图</div>
  </div>
</template>

<script>
export default {
  props: { input: String, quickPhrases: Array, quoteMsg: Object, kaomojis: Array },
  emits: ['update:input', 'send', 'clear-quote'],
  data() { return { text: '', showEmoji: false, placeholderText: '输入消息…', _placeIdx: 0 } },
  watch: { input(v) { if (v !== undefined && v !== this.text) this.text = v } },
  created() { this.text = this.input || ''; this._placeTimer = setInterval(() => { const tips = ['输入消息…', '说「提醒我明天9点开会」', '说「/reroll」重新生成', '直接聊天也行…']; this._placeIdx = (this._placeIdx + 1) % tips.length; this.placeholderText = tips[this._placeIdx] }, 5000) },
  beforeUnmount() { if (this._placeTimer) { clearInterval(this._placeTimer); this._placeTimer = null } },
  methods: {
    send() { const msg = this.text.trim(); if (!msg) return; this.$emit('send', msg); this.text = ''; this.showEmoji = false },
    newline() { this.text += '\n'; this.resize() },
    insertEmoji(k) { this.text += k; this.showEmoji = false; this.$refs.el?.focus(); this.resize() },
    resize() { this.$nextTick(() => { const el = this.$refs.el; if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px' } }) },
  }
}
</script>

<style scoped>
.chat-input-area { padding: 10px 16px 8px; border-top: 1px solid var(--border); background: var(--cb); }
.quick-bar { display: flex; gap: 6px; padding-bottom: 6px; flex-wrap: wrap; }
.qp-chip { padding: 3px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border); border-radius: 14px; font-size: 11px; color: var(--tc2); cursor: pointer; }
.qp-chip:hover { background: var(--p); color: #fff; border-color: var(--p); }
.quote-bar { display: flex; align-items: center; gap: 8px; padding: 4px 10px; background: rgba(255,255,255,.03); border-left: 2px solid var(--p); border-radius: 4px; margin-bottom: 6px; font-size: 12px; }
.quote-preview { flex: 1; color: var(--tc2); }
.quote-close { background: none; border: none; color: var(--tc2); cursor: pointer; font-size: 14px; }
.input-row { display: flex; align-items: flex-end; gap: 8px; position: relative; }
.emoji-btn { background: none; border: 1px solid var(--border); border-radius: 4px; color: var(--tc2); font-size: 14px; padding: 6px 8px; cursor: pointer; }
.emoji-btn:hover { background: rgba(255,255,255,.04); }
.emoji-picker { position: absolute; bottom: 44px; left: 0; background: var(--sb); border: 1px solid var(--border); border-radius: 6px; padding: 8px; display: flex; flex-wrap: wrap; gap: 4px; width: 260px; z-index: 100; }
.emoji-item { font-size: 13px; padding: 4px 6px; cursor: pointer; border-radius: 4px; color: var(--tc); }
.emoji-item:hover { background: rgba(255,255,255,.06); }
.chat-input { flex: 1; padding: 8px 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--tc); font-size: 14px; resize: none; outline: none; font-family: inherit; line-height: 1.5; }
.chat-input:focus { border-color: var(--p); }
.send-btn { padding: 8px 20px; background: var(--p); color: #fff; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; }
.send-btn:disabled { opacity: .4; cursor: default; }
.send-btn:not(:disabled):hover { filter: brightness(1.1); }
.input-hint { text-align: center; font-size: 10px; color: var(--tc2); padding-top: 4px; opacity: .5; }

/* 移动端适配 */
@media (max-width: 768px) {
  .chat-input-area {
    padding: 8px 12px 12px;
    padding-bottom: calc(12px + env(safe-area-inset-bottom, 0));
  }
  .input-row {
    align-items: center;
  }
  .qp-chip {
    padding: 6px 14px;
    font-size: 12px;
    min-height: 36px;
    display: flex;
    align-items: center;
  }
  .emoji-btn {
    min-width: 44px;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .send-btn {
    min-height: 44px;
    padding: 8px 24px;
    font-size: 14px;
  }
  .chat-input {
    font-size: 16px; /* 防止 iOS 自动缩放 */
    padding: 10px 12px;
    min-height: 44px;
    line-height: 1.4;
  }
  .input-hint { font-size: 11px; }
}
</style>
