<template>
  <div class="panel-view">
    <div class="panel-header">
      <h2>设置</h2>
    </div>

    <!-- Connection -->
    <div class="settings-section">
      <div class="section-title">连接</div>
      <div class="setting-item">
        <label>服务器地址</label>
        <input class="input-field" v-model="host" placeholder="192.168.x.x:8060" @change="saveHost" />
      </div>
      <div class="setting-item">
        <label>API Token</label>
        <input class="input-field" type="password" v-model="token" placeholder="留空则无认证" @change="saveToken" />
      </div>
      <div class="setting-item">
        <label>状态</label>
        <div class="conn-status">
          <span :class="['status-dot', chat.wsReady ? 'online' : 'offline']"></span>
          <span :class="['status-text', chat.wsReady ? 'online' : 'offline']">
            {{ chat.wsReady ? '已连接' : '未连接' }}
          </span>
          <button v-if="!chat.wsReady" class="reconnect-btn" @click="reconnect">重连</button>
        </div>
      </div>
    </div>

    <!-- Sessions -->
    <div class="settings-section">
      <div class="section-title">会话</div>
      <div v-for="s in chat.sessions" :key="s.id" :class="['session-item', { active: s.id === chat.activeSessionId }]">
        <span class="session-name">{{ s.name || '未命名' }}</span>
        <span class="session-count">{{ s.message_count || 0 }}条</span>
        <div class="session-actions">
          <button v-if="s.id !== chat.activeSessionId" class="small-btn" @click="switchS(s.id)">切换</button>
          <button v-if="s.id !== chat.activeSessionId" class="small-btn danger" @click="deleteS(s.id)">删除</button>
        </div>
      </div>
      <button class="add-session-btn" @click="createS">+ 新建会话</button>
    </div>

    <!-- LLM -->
    <div class="settings-section">
      <div class="section-title">LLM</div>
      <div class="setting-item">
        <label>API Key</label>
        <input class="input-field" type="password" v-model="form.api_key" @change="save('api_key', form.api_key)" />
      </div>
      <div class="setting-item">
        <label>Provider</label>
        <select class="input-field" v-model="form.api_provider" @change="save('api_provider', form.api_provider)">
          <option value="">默认</option>
          <option value="deepseek">DeepSeek</option>
          <option value="openai">OpenAI</option>
          <option value="ollama">Ollama</option>
          <option value="mimo">MiMo</option>
          <option value="siliconflow">SiliconFlow</option>
        </select>
      </div>
      <div class="setting-item">
        <label>Base URL</label>
        <input class="input-field" v-model="form.api_base_url" @change="save('api_base_url', form.api_base_url)" />
      </div>
      <div class="setting-item">
        <label>Model</label>
        <input class="input-field" v-model="form.api_model" @change="save('api_model', form.api_model)" />
      </div>
    </div>

    <!-- Persona -->
    <div class="settings-section">
      <div class="section-title">Persona</div>
      <div class="setting-item">
        <label>你的名字</label>
        <input class="input-field" v-model="form.user_name" @change="save('user_name', form.user_name)" />
      </div>
      <div class="setting-item">
        <label>AI 名字</label>
        <input class="input-field" v-model="form.ai_name" @change="save('ai_name', form.ai_name)" />
      </div>
    </div>

    <!-- Voice -->
    <div class="settings-section">
      <div class="section-title">Voice</div>
      <div class="setting-item">
        <label>TTS</label>
        <button :class="['toggle-btn', { on: form.tts_enabled }]" @click="form.tts_enabled = !form.tts_enabled; save('voice', { tts_enabled: form.tts_enabled })">
          {{ form.tts_enabled ? 'ON' : 'OFF' }}
        </button>
      </div>
    </div>

    <!-- Danger -->
    <div class="settings-section danger">
      <div class="section-title">危险操作</div>
      <button class="danger-btn" @click="fullReset">完全重置</button>
    </div>

    <div class="app-info">
      <span>Vesper Mobile v1.0</span>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useAppStore } from '../stores/appStore.js'
import { useChatStore } from '../stores/chatStore.js'
import api from '../api.js'

const app = useAppStore()
const chat = useChatStore()

const host = ref(localStorage.getItem('vesper_host') || '')
const token = ref(localStorage.getItem('vesper_api_token') || '')

const form = reactive({
  api_key: '', api_provider: '', api_base_url: '', api_model: '',
  user_name: '', ai_name: '', tts_enabled: false,
})

function saveHost() {
  const val = host.value.trim()
  if (val) {
    localStorage.setItem('vesper_host', val)
  } else {
    localStorage.removeItem('vesper_host')
  }
  chat.disconnect()
  chat.connectWebSocket()
  app.showToast('已保存，重新连接中')
}

function saveToken() {
  const val = token.value.trim()
  if (val) {
    localStorage.setItem('vesper_api_token', val)
  } else {
    localStorage.removeItem('vesper_api_token')
  }
}

function reconnect() {
  chat.disconnect()
  chat.connectWebSocket()
  app.showToast('正在重连...')
}

async function createS() {
  const name = prompt('会话名称:', '')
  if (name === null) return
  await chat.createSession(name || '新会话')
  app.showToast('已创建')
}

async function switchS(id) {
  await chat.switchSession(id)
  app.showToast('已切换')
}

async function deleteS(id) {
  if (!confirm('删除此会话？')) return
  await chat.deleteSession(id)
  app.showToast('已删除')
}

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
  chat.loadSessions()
})

async function save(key, value) {
  try {
    await api.post('/settings/', { key, value })
    app.showToast('已保存')
  } catch {}
}

async function fullReset() {
  if (!confirm('此操作将删除所有数据，确定？')) return
  if (!confirm('再次确认：所有聊天记录、角色、设置都将被删除！')) return
  try {
    await api.post('/settings/full-reset', { confirm: true })
    location.reload()
  } catch {}
}
</script>
