<template>
  <div class="panel-view">
    <div class="panel-title">/characters</div>

    <div style="display: flex; gap: 8px; margin-bottom: 16px;">
      <button class="btn btn-accent" @click="showImport = true">Import</button>
      <button class="btn" @click="showCreate = true">New</button>
    </div>

    <div style="display: flex; flex-direction: column; gap: 8px;">
      <div v-for="c in characters" :key="c.id"
        :class="['char-card', { active: c.is_active }]"
        @click="app.activateCharacter(c.id)">
        <div class="char-avatar">
          <img v-if="c.avatar" :src="`/avatars/${c.avatar}`" />
          <div v-else class="char-avatar-fallback">{{ (c.name || '?')[0] }}</div>
        </div>
        <div class="char-info">
          <div class="char-name">{{ c.name }}</div>
          <div class="char-desc">{{ (c.description || '').slice(0, 80) }}</div>
        </div>
        <span v-if="c.is_active" class="char-badge">active</span>
        <button v-if="!c.is_active" class="btn" @click.stop="app.activateCharacter(c.id)" style="font-size: 12px; padding: 4px 10px;">Use</button>
        <button class="btn btn-danger" @click.stop="delChar(c.id)" style="font-size: 12px; padding: 4px 8px;">x</button>
      </div>
      <div v-if="!characters.length" style="text-align: center; padding: 40px; color: var(--text-muted);">No characters yet</div>
    </div>

    <!-- Import Modal -->
    <div v-if="showImport" class="modal-overlay" @click.self="showImport = false">
      <div class="modal-box">
        <div class="modal-title">Import Character Card</div>
        <div class="setting-group">
          <div class="setting-label">Format</div>
          <div style="display: flex; gap: 8px; margin-bottom: 12px;">
            <button :class="['btn', importTab === 'json' ? 'btn-accent' : '']" @click="importTab = 'json'">JSON</button>
            <button :class="['btn', importTab === 'png' ? 'btn-accent' : '']" @click="importTab = 'png'">PNG</button>
          </div>
          <div v-if="importTab === 'json'">
            <textarea v-model="importJson" class="setting-input" style="width: 100%; min-height: 120px; font-family: var(--font-mono); font-size: 12px;" placeholder="Paste character card JSON..."></textarea>
          </div>
          <div v-else>
            <input type="file" accept=".png" @change="importPng" />
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn" @click="showImport = false">Cancel</button>
          <button class="btn btn-accent" v-if="importTab === 'json'" @click="doImportJson">Import</button>
        </div>
      </div>
    </div>

    <!-- Create Modal -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal-box">
        <div class="modal-title">New Character</div>
        <div class="setting-group">
          <div class="setting-label">Name</div>
          <input class="setting-input" v-model="newName" placeholder="Character name" style="width: 100%; margin-bottom: 12px;" />
          <div class="setting-label">Description</div>
          <textarea class="setting-input" v-model="newDesc" placeholder="Description..." style="width: 100%; min-height: 80px;"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn" @click="showCreate = false">Cancel</button>
          <button class="btn btn-accent" @click="doCreate" :disabled="!newName">Create</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/appStore.js'
import api from '../api.js'

const app = useAppStore()
const characters = ref([])
const showImport = ref(false)
const showCreate = ref(false)
const importTab = ref('json')
const importJson = ref('')
const newName = ref('')
const newDesc = ref('')

async function loadChars() {
  try {
    const res = await api.get('/characters/')
    characters.value = res.data.characters || []
  } catch {}
}

async function doImportJson() {
  try {
    const data = JSON.parse(importJson.value)
    await api.post('/characters/import/json', data)
    importJson.value = ''
    showImport.value = false
    await loadChars()
    app.showToast('Imported')
  } catch (e) {
    app.showToast('JSON parse error')
  }
}

async function importPng(e) {
  const file = e.target.files[0]
  if (!file) return
  const form = new FormData()
  form.append('file', file)
  try {
    await api.post('/characters/import/png', form)
    showImport.value = false
    await loadChars()
    app.showToast('Imported')
  } catch {
    app.showToast('PNG parse error')
  }
}

async function doCreate() {
  if (!newName.value) return
  try {
    await api.post('/characters/', { name: newName.value, description: newDesc.value })
    newName.value = ''
    newDesc.value = ''
    showCreate.value = false
    await loadChars()
  } catch {}
}

async function delChar(id) {
  if (!confirm('Delete this character?')) return
  try {
    await api.delete(`/characters/${id}`)
    await loadChars()
  } catch {}
}

onMounted(loadChars)
</script>
