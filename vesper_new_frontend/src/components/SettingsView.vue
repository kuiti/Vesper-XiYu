<template>
  <div class="panel-view">
    <div class="panel-title">/settings</div>

    <div class="setting-group">
      <div class="setting-label">LLM</div>
      <div class="setting-row">
        <span class="setting-name">API Key</span>
        <input class="setting-input" type="password" v-model="form.api_key" @change="save('api_key', form.api_key)" />
      </div>
      <div class="setting-row">
        <span class="setting-name">Provider</span>
        <select class="setting-select" v-model="form.api_provider" @change="save('api_provider', form.api_provider)">
          <option value="">Default</option>
          <option value="deepseek">DeepSeek</option>
          <option value="openai">OpenAI</option>
          <option value="ollama">Ollama</option>
          <option value="mimo">MiMo</option>
          <option value="siliconflow">SiliconFlow</option>
        </select>
      </div>
      <div class="setting-row">
        <span class="setting-name">Base URL</span>
        <input class="setting-input" v-model="form.api_base_url" @change="save('api_base_url', form.api_base_url)" />
      </div>
      <div class="setting-row">
        <span class="setting-name">Model</span>
        <input class="setting-input" v-model="form.api_model" @change="save('api_model', form.api_model)" />
      </div>
    </div>

    <div class="setting-group">
      <div class="setting-label">Persona</div>
      <div class="setting-row">
        <span class="setting-name">User Name</span>
        <input class="setting-input" v-model="form.user_name" @change="save('user_name', form.user_name)" />
      </div>
      <div class="setting-row">
        <span class="setting-name">AI Name</span>
        <input class="setting-input" v-model="form.ai_name" @change="save('ai_name', form.ai_name)" />
      </div>
    </div>

    <div class="setting-group">
      <div class="setting-label">Voice</div>
      <div class="setting-row">
        <span class="setting-name">TTS Enabled</span>
        <button :class="['btn', form.tts_enabled ? 'btn-accent' : '']" @click="form.tts_enabled = !form.tts_enabled; save('voice', { tts_enabled: form.tts_enabled })">
          {{ form.tts_enabled ? 'ON' : 'OFF' }}
        </button>
      </div>
    </div>

    <div class="setting-group">
      <div class="setting-label">Danger Zone</div>
      <button class="btn btn-danger" @click="fullReset">Full Reset</button>
    </div>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue'
import { useAppStore } from '../stores/appStore.js'
import api from '../api.js'

const app = useAppStore()

const form = reactive({
  api_key: '', api_provider: '', api_base_url: '', api_model: '',
  user_name: '', ai_name: '', tts_enabled: false,
})

onMounted(async () => {
  await app.loadSettings()
  const s = app.settings
  form.api_key = s.has_api_key ? '***' : ''
  form.api_provider = s.api_provider || ''
  form.api_base_url = s.api_base_url || ''
  form.api_model = s.api_model || ''
  form.user_name = s.user_name || ''
  form.ai_name = s.ai_name || ''
  form.tts_enabled = s.tts_enabled || false
})

async function save(key, value) {
  try {
    await api.post('/settings/', { key, value })
    app.showToast('Saved')
  } catch {}
}

async function fullReset() {
  if (!confirm('This will delete all data. Are you sure?')) return
  try {
    await api.post('/settings/full-reset', { confirm: true })
    location.reload()
  } catch {}
}
</script>
