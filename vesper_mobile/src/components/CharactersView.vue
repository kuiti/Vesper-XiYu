<template>
  <div class="panel-view">
    <!-- List View -->
    <div v-if="!detailChar" class="char-list-view">
      <div class="panel-header">
        <h2>角色</h2>
        <div class="panel-actions">
          <button class="icon-btn" @click="showImport = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </button>
          <button class="icon-btn" @click="showCreate = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
        </div>
      </div>

      <div class="char-list">
        <div v-for="c in characters" :key="c.id"
          :class="['char-card', { active: c.is_active }]"
          @click="openDetail(c)">
          <div class="char-avatar">
            <img v-if="c.avatar" :src="`/avatars/${c.avatar}`" />
            <div v-else class="avatar-fallback">{{ (c.name || '?')[0] }}</div>
          </div>
          <div class="char-info">
            <div class="char-name">{{ c.name }}</div>
            <div class="char-desc">{{ (c.description || '').slice(0, 60) }}</div>
          </div>
          <span v-if="c.is_active" class="active-badge">使用中</span>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" style="color: var(--text-muted)"><polyline points="9 18 15 12 9 6"/></svg>
        </div>
        <div v-if="!characters.length && !app.isLoadingChars" class="empty-msg">
          <p>暂无角色</p>
          <p style="font-size: 12px; margin-top: 8px;">点击右上角 + 创建或导入</p>
        </div>
      </div>
    </div>

    <!-- Detail View -->
    <div v-else class="char-detail">
      <div class="detail-header">
        <button class="back-btn" @click="detailChar = null">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><polyline points="15 18 9 12 15 6"/></svg>
        </button>
        <h2>{{ detailChar.name }}</h2>
        <div style="width: 36px"></div>
      </div>

      <div class="detail-avatar">
        <img v-if="detailChar.avatar" :src="`/avatars/${detailChar.avatar}`" />
        <div v-else class="avatar-fallback-xl">{{ (detailChar.name || '?')[0] }}</div>
      </div>

      <div class="detail-section">
        <div class="section-label">描述</div>
        <div class="section-content">{{ detailChar.description || '无' }}</div>
      </div>

      <div v-if="detailChar.personality" class="detail-section">
        <div class="section-label">性格</div>
        <div class="section-content">{{ detailChar.personality }}</div>
      </div>

      <div v-if="detailChar.scenario" class="detail-section">
        <div class="section-label">场景</div>
        <div class="section-content">{{ detailChar.scenario }}</div>
      </div>

      <div class="detail-actions">
        <button v-if="!detailChar.is_active" class="primary-btn" @click="activateChar(detailChar)">使用此角色</button>
        <button v-else class="primary-btn active-state" disabled>当前使用中</button>
        <button class="danger-btn" @click="deleteChar(detailChar)">删除角色</button>
      </div>
    </div>

    <!-- Import Sheet -->
    <Transition name="sheet">
      <div v-if="showImport" class="action-sheet-overlay" @click.self="showImport = false">
        <div class="action-sheet">
          <div class="action-sheet-title">导入角色卡</div>
          <div class="import-tabs">
            <button :class="['tab-btn', { active: importTab === 'json' }]" @click="importTab = 'json'">JSON</button>
            <button :class="['tab-btn', { active: importTab === 'png' }]" @click="importTab = 'png'">PNG</button>
          </div>
          <div v-if="importTab === 'json'" class="import-body">
            <textarea v-model="importJson" class="input-area-field" placeholder="粘贴角色卡 JSON..." rows="4"></textarea>
            <button class="primary-btn" @click="doImportJson" style="margin-top: 8px">导入</button>
          </div>
          <div v-else class="import-body">
            <label class="file-label">
              <input type="file" accept=".png" @change="importPng" hidden />
              <span class="primary-btn">选择 PNG 文件</span>
            </label>
          </div>
          <button class="cancel-btn" @click="showImport = false" style="margin-top: 8px">取消</button>
        </div>
      </div>
    </Transition>

    <!-- Create Sheet -->
    <Transition name="sheet">
      <div v-if="showCreate" class="action-sheet-overlay" @click.self="showCreate = false">
        <div class="action-sheet">
          <div class="action-sheet-title">新建角色</div>
          <div class="form-group">
            <label>名称</label>
            <input class="input-field" v-model="newName" placeholder="角色名称" />
          </div>
          <div class="form-group">
            <label>描述</label>
            <textarea class="input-area-field" v-model="newDesc" placeholder="角色描述..." rows="3"></textarea>
          </div>
          <div class="sheet-btns">
            <button class="cancel-btn" @click="showCreate = false">取消</button>
            <button class="primary-btn" @click="doCreate" :disabled="!newName">创建</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/appStore.js'

const app = useAppStore()
const characters = ref([])
const showImport = ref(false)
const showCreate = ref(false)
const importTab = ref('json')
const importJson = ref('')
const newName = ref('')
const newDesc = ref('')
const detailChar = ref(null)

async function loadChars() {
  await app.loadCharacters()
  characters.value = app.characters
}

function openDetail(c) {
  detailChar.value = c
}

async function activateChar(c) {
  await app.activateCharacter(c.id)
  detailChar.value = null
  await loadChars()
}

async function deleteChar(c) {
  if (!confirm(`确定删除 "${c.name}"？`)) return
  await app.deleteCharacter(c.id)
  detailChar.value = null
  await loadChars()
}

async function doImportJson() {
  try {
    await app.importCharacterJson(importJson.value)
    importJson.value = ''
    showImport.value = false
    await loadChars()
    app.showToast('导入成功')
  } catch {
    app.showToast('JSON 解析失败')
  }
}

async function importPng(e) {
  const file = e.target.files[0]
  if (!file) return
  try {
    await app.importCharacterPng(file)
    showImport.value = false
    await loadChars()
    app.showToast('导入成功')
  } catch {
    app.showToast('PNG 解析失败')
  }
}

async function doCreate() {
  if (!newName.value) return
  try {
    await app.createCharacter(newName.value, newDesc.value)
    newName.value = ''
    newDesc.value = ''
    showCreate.value = false
    await loadChars()
  } catch {
    app.showToast('创建失败')
  }
}

onMounted(loadChars)
</script>
