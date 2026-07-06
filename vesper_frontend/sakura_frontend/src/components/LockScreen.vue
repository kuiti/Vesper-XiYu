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
import api from '../api'

export default {
  props: { onUnlock: Function },
  emits: ['unlock'],
  data() { return { pin: '', error: '', attempts: 0, showReset: false, _coolTimer: null } },
  methods: {
    submit() {
      if (this._coolTimer) { return }
      const cool = Math.min(30000 * Math.pow(2, this.attempts - 4), 300000)
      if (this.attempts >= 5) { this.error = `尝试次数过多，请${Math.ceil(cool/1000)}秒后再试`; return }
      if (this.onUnlock) {
        const ok = this.onUnlock(this.pin)
        if (!ok) { this.pin = ''; this.error = 'PIN 不正确'; this.attempts++; if (this.attempts >= 5) { const t = Math.min(30000 * Math.pow(2, this.attempts - 5), 300000); this.error = `尝试次数过多，请${Math.ceil(t/1000)}秒后再试`; this._coolTimer = setTimeout(() => { this._coolTimer = null; this.attempts = 0; this.error = '' }, t) } }
      }
    },
    doReset() {
      try {
        localStorage.setItem('_reset_pin', '1')
        location.reload()
      } catch (e) { this.error = '重置失败，请手动删除 data/sakura.db 中 config 表的 pin_code 记录' }
    }
  }
}
</script>

<style scoped>
.lock-overlay { position: fixed; inset: 0; background: var(--surface-app); z-index: 9999; display: flex; align-items: center; justify-content: center; }
.lock-card { text-align: center; color: var(--text-primary); }
.lock-card h3 { font-size: 18px; font-weight: 400; margin-bottom: 16px; }
.pin-input { width: 120px; padding: 10px; font-size: 24px; text-align: center; letter-spacing: 8px; border-radius: 6px; border: 1px solid var(--border-default); background: var(--surface-sidebar); color: var(--text-primary); outline: none; }
.pin-input:focus { border-color: var(--accent-primary); }
.pin-error { color: #e74c3c; font-size: 13px; margin-top: 8px; }
.lock-actions { margin-top: 12px; }
.forgot-btn { background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 12px; text-decoration: underline; opacity: .6; }
.forgot-btn:hover { opacity: 1; }
.reset-box { margin-top: 8px; }
.reset-hint { color: var(--text-secondary); font-size: 12px; margin-bottom: 8px; }
.reset-btn { background: #e74c3c; border: none; color: #fff; border-radius: 4px; padding: 6px 14px; cursor: pointer; font-size: 12px; margin-right: 6px; }
.cancel-btn { background: var(--surface-sidebar); border: 1px solid var(--border-default); color: var(--text-primary); border-radius: 4px; padding: 6px 14px; cursor: pointer; font-size: 12px; }
</style>
