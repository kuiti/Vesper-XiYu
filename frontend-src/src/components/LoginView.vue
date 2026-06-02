<template>
  <div class="login-overlay">
    <div class="login-card">
      <div class="login-icon">🔐</div>
      <h2>夕语</h2>
      <p class="login-hint">云端模式 · 请输入访问令牌</p>
      <input
        type="password"
        v-model="token"
        placeholder="输入 Token"
        @keyup.enter="login"
        class="login-input"
        autofocus
      />
      <div v-if="error" class="login-error">{{ error }}</div>
      <button class="login-btn" @click="login" :disabled="loading">
        {{ loading ? '验证中...' : '登录' }}
      </button>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  name: 'LoginView',
  data() {
    return {
      token: '',
      error: '',
      loading: false,
    }
  },
  mounted() {
    // 检查是否有保存的 Token
    const saved = localStorage.getItem('vesper_api_token')
    if (saved) {
      this.token = saved
      this.login()
    }
  },
  methods: {
    async login() {
      if (!this.token.trim()) {
        this.error = '请输入 Token'
        return
      }
      this.loading = true
      this.error = ''
      try {
        const res = await api.post('/auth/verify', { token: this.token })
        if (res.data?.ok) {
          localStorage.setItem('vesper_api_token', this.token)
          this.$emit('login-success', this.token)
        } else {
          this.error = res.data?.error || '验证失败'
        }
      } catch (e) {
        if (e.response?.status === 429) {
          this.error = e.response.data?.error || '尝试次数过多'
        } else if (e.response?.status === 401) {
          this.error = 'Token 不正确'
        } else {
          this.error = '连接失败，请检查网络'
        }
      }
      this.loading = false
    },
  },
}
</script>

<style scoped>
.login-overlay {
  position: fixed;
  inset: 0;
  background: #0a0d1a;
  z-index: 99999;
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-card {
  text-align: center;
  color: #e0e0e0;
  width: 90vw;
  max-width: 320px;
}
.login-icon {
  font-size: 48px;
  margin-bottom: 16px;
}
.login-card h2 {
  font-size: 24px;
  font-weight: 400;
  margin-bottom: 8px;
  color: #fff;
}
.login-hint {
  font-size: 13px;
  color: #888;
  margin-bottom: 24px;
}
.login-input {
  width: 100%;
  padding: 12px 16px;
  font-size: 16px;
  border-radius: 8px;
  border: 1px solid #333;
  background: #111;
  color: #fff;
  outline: none;
  box-sizing: border-box;
}
.login-input:focus {
  border-color: #6a9fd8;
}
.login-error {
  color: #e74c3c;
  font-size: 13px;
  margin-top: 8px;
}
.login-btn {
  width: 100%;
  padding: 12px;
  font-size: 16px;
  border-radius: 8px;
  border: none;
  background: #6a9fd8;
  color: #fff;
  cursor: pointer;
  margin-top: 16px;
}
.login-btn:hover {
  background: #5a8fc8;
}
.login-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
