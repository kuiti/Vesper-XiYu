<template>
  <div class="lock-overlay">
    <div class="lock-card">
      <h3>已锁定</h3>
      <input type="password" v-model="pin" placeholder="输入PIN" @keyup.enter="submit" class="pin-input" autofocus>
      <div v-if="error" class="pin-error">{{ error }}</div>
      <div class="lock-actions">
        <button class="forgot-btn" v-if="attempts >= 3 && !showReset" @click="showReset = true">忘记PIN?</button>
        <div v-if="showReset" class="reset-box">
          <p class="reset-hint">重置将清除PIN码，聊天记录和记忆不会丢失。</p>
          <button class="reset-btn" @click="doReset">确认重置</button>
          <button class="cancel-btn" @click="showReset = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  props: { onUnlock: Function },
  emits: ['unlock'],
  data() { return { pin: '', error: '', attempts: 0, showReset: false } },
  methods: {
    submit() {
      if (this.attempts >= 5) { this.error = '尝试次数过多，请30秒后再试'; return }
      if (this.onUnlock) {
        const ok = this.onUnlock(this.pin)
        if (!ok) { this.pin = ''; this.error = 'PIN 不正确'; this.attempts++; if (this.attempts >= 5) { this._coolTimer = setTimeout(() => { this.attempts = 0; this.error = '' }, 30000) } }
      }
    },
    doReset() {
      try {
        localStorage.setItem('_reset_pin', '1')
        location.reload()
      } catch (e) { this.error = '重置失败，请手动删除 data/vesper.db 中 config 表的 pin_code 记录' }
    }
  }
}
</script>

<style scoped>
.lock-overlay { position: fixed; inset: 0; background: var(--bg); z-index: 9999; display: flex; align-items: center; justify-content: center; }
.lock-card { text-align: center; color: var(--tc); }
.lock-card h3 { font-size: 18px; font-weight: 400; margin-bottom: 16px; }
.pin-input { width: 120px; padding: 10px; font-size: 24px; text-align: center; letter-spacing: 8px; border-radius: 6px; border: 1px solid var(--border); background: var(--sb); color: var(--tc); outline: none; }
.pin-input:focus { border-color: var(--p); }
.pin-error { color: #e74c3c; font-size: 13px; margin-top: 8px; }
.lock-actions { margin-top: 12px; }
.forgot-btn { background: none; border: none; color: var(--tc2); cursor: pointer; font-size: 12px; text-decoration: underline; opacity: .6; }
.forgot-btn:hover { opacity: 1; }
.reset-box { margin-top: 8px; }
.reset-hint { color: var(--tc2); font-size: 12px; margin-bottom: 8px; }
.reset-btn { background: #e74c3c; border: none; color: #fff; border-radius: 4px; padding: 6px 14px; cursor: pointer; font-size: 12px; margin-right: 6px; }
.cancel-btn { background: var(--sb); border: 1px solid var(--border); color: var(--tc); border-radius: 4px; padding: 6px 14px; cursor: pointer; font-size: 12px; }
</style>
