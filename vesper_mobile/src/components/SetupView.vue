<template>
  <div class="setup-screen">
    <div class="setup-content">
      <div class="setup-logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="64" height="64">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
        </svg>
      </div>
      <h1 class="setup-title">夕语</h1>
      <p class="setup-sub">连接到你的夕语后端服务</p>

      <div class="setup-form">
        <div class="form-group">
          <label>服务器地址</label>
          <input
            class="setup-input"
            v-model="host"
            placeholder="192.168.x.x:8060"
            @keydown.enter="connect"
            autofocus
          />
          <p class="form-hint">输入夕语后端的 IP 地址和端口</p>
        </div>

        <div class="form-group">
          <label>API Token (可选)</label>
          <input
            class="setup-input"
            type="password"
            v-model="token"
            placeholder="留空则无认证"
          />
          <p class="form-hint">如果后端启用了认证，填写 Token</p>
        </div>

        <button class="setup-btn" @click="connect" :disabled="!host.trim()">
          连接
        </button>

        <div v-if="error" class="setup-error">{{ error }}</div>
      </div>

      <div class="setup-tips">
        <p>确保手机和后端在同一网络</p>
        <p>后端默认端口 8060</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['connect'])

const host = ref(localStorage.getItem('vesper_host') || '')
const token = ref(localStorage.getItem('vesper_api_token') || '')
const error = ref('')

function connect() {
  const h = host.value.trim()
  if (!h) {
    error.value = '请输入服务器地址'
    return
  }

  // Validate format
  if (!h.includes(':') && !h.includes('.')) {
    error.value = '地址格式不正确，应为 IP:端口'
    return
  }

  // Save
  localStorage.setItem('vesper_host', h)
  if (token.value.trim()) {
    localStorage.setItem('vesper_api_token', token.value.trim())
  } else {
    localStorage.removeItem('vesper_api_token')
  }

  error.value = ''
  emit('connect')
}
</script>
