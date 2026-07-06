<template>
  <div class="characters-view">
    <div class="cv-header">
      <h2>角色卡</h2>
      <div class="cv-actions">
        <button class="btn-s" @click="showImport = !showImport">导入</button>
        <button class="btn" @click="saveCurrent" :disabled="saving">{{ saving ? '保存中...' : '保存当前' }}</button>
      </div>
    </div>

    <!-- 导入区域 -->
    <div v-if="showImport" class="import-area">
      <textarea v-model="importJson" placeholder="粘贴角色卡 JSON" rows="4"></textarea>
      <div class="import-btns">
        <button class="btn" @click="importJsonCard">导入 JSON</button>
        <label class="btn-s file-label">
          导入 PNG
          <input type="file" accept=".png" @change="importPngCard" style="display:none" />
        </label>
      </div>
      <div v-if="importError" class="err-msg">{{ importError }}</div>
    </div>

    <!-- 当前角色 -->
    <div class="current-card" v-if="currentCard">
      <h3>当前角色</h3>
      <div class="card-info">
        <div class="card-name">{{ currentCard.name || '未命名' }}</div>
        <div class="card-meta">
          <span class="tag" v-if="currentCard.tone">语气: {{ currentCard.tone }}</span>
          <span class="tag" v-if="currentCard.foundation_type">基石: {{ currentCard.foundation_type }}</span>
        </div>
        <div class="card-desc" v-if="currentCard.description">{{ currentCard.description }}</div>
      </div>
    </div>

    <!-- 角色卡列表 -->
    <h3>已保存的角色卡</h3>
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="cards.length === 0" class="empty">暂无保存的角色卡</div>
    <div v-else class="card-list">
      <div v-for="card in cards" :key="card.name" class="card-item">
        <div class="card-body">
          <div class="card-name">{{ card.name }}</div>
          <div class="card-desc">{{ card.description || '无描述' }}</div>
          <div class="card-tags">
            <span class="tag" v-if="card.tone">语气: {{ card.tone }}</span>
            <span v-for="t in (card.tags||[])" :key="t" class="tag">{{ t }}</span>
          </div>
        </div>
        <div class="card-actions">
          <button class="btn" @click="applyCard(card.name)" :disabled="applying === card.name">
            {{ applying === card.name ? '应用中...' : '应用' }}
          </button>
          <button class="btn-s danger" @click="deleteCard(card.name)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api'

export default {
  data() {
    return {
      cards: [],
      currentCard: null,
      loading: false,
      saving: false,
      applying: null,
      showImport: false,
      importJson: '',
      importError: ''
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true
      try {
        const [listRes, curRes] = await Promise.all([
          api.get('/characters/'),
          api.get('/characters/current')
        ])
        this.cards = listRes.data.characters || []
        const cur = curRes.data.character || {}
        this.currentCard = {
          name: cur.name,
          description: cur.description,
          tone: (cur.extensions?.sakura || {}).tone,
          foundation_type: (cur.extensions?.sakura || {}).foundation_type
        }
      } catch (e) { console.error(e) }
      finally { this.loading = false }
    },
    async saveCurrent() {
      this.saving = true
      try {
        const res = await api.post('/characters/current/save')
        await this.load()
      } catch (e) { console.error(e) }
      finally { this.saving = false }
    },
    async applyCard(name) {
      this.applying = name
      try {
        await api.post('/characters/current/apply', { name })
        await this.load()
      } catch (e) { console.error(e) }
      finally { this.applying = null }
    },
    async deleteCard(name) {
      if (!confirm(`删除角色卡「${name}」？`)) return
      try {
        await api.delete(`/characters/${encodeURIComponent(name)}`)
        await this.load()
      } catch (e) { console.error(e) }
    },
    async importJsonCard() {
      if (!this.importJson.trim()) return
      this.importError = ''
      try {
        const data = JSON.parse(this.importJson)
        await api.post('/characters/import/json', data)
        this.importJson = ''
        this.showImport = false
        await this.load()
      } catch (e) {
        this.importError = e.response?.data?.detail || e.message || '导入失败'
      }
    },
    async importPngCard(e) {
      const file = e.target.files[0]
      if (!file) return
      this.importError = ''
      const fd = new FormData()
      fd.append('file', file)
      try {
        await api.post('/characters/import/png', fd)
        await this.load()
      } catch (e) {
        this.importError = e.response?.data?.detail || e.message || '导入失败'
      }
    }
  }
}
</script>

<style scoped>
.characters-view { padding: 20px; overflow-y: auto; height: 100%; }
.cv-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.cv-header h2 { font-size: 18px; font-weight: 600; color: var(--text-primary); margin: 0; }
.cv-actions { display: flex; gap: 8px; }
.import-area { background: var(--surface-sidebar); border: 1px solid var(--border-default); border-radius: 8px; padding: 12px; margin-bottom: 16px; }
.import-area textarea { width: 100%; box-sizing: border-box; background: var(--surface-app); color: var(--text-primary); border: 1px solid var(--border-default); border-radius: 6px; padding: 8px; font-size: 12px; resize: vertical; }
.import-btns { display: flex; gap: 8px; margin-top: 8px; }
.err-msg { color: #e74c3c; font-size: 12px; margin-top: 6px; }
.current-card { background: var(--surface-sidebar); border: 1px solid var(--accent-primary); border-radius: 8px; padding: 12px; margin-bottom: 16px; }
.current-card h3 { font-size: 13px; color: var(--text-secondary); margin: 0 0 8px 0; }
.card-info { display: flex; flex-direction: column; gap: 4px; }
.card-name { font-size: 16px; font-weight: 600; color: var(--accent-primary); }
.card-meta { display: flex; gap: 6px; flex-wrap: wrap; }
.tag { background: var(--border-default); color: var(--text-secondary); font-size: 11px; padding: 2px 8px; border-radius: 10px; }
.card-list { display: flex; flex-direction: column; gap: 8px; }
.card-item { background: var(--surface-sidebar); border: 1px solid var(--border-default); border-radius: 8px; padding: 12px; display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.card-body { flex: 1; min-width: 0; }
.card-desc { font-size: 12px; color: var(--text-secondary); margin: 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.card-actions { display: flex; gap: 6px; flex-shrink: 0; }
.loading, .empty { text-align: center; color: var(--text-secondary); font-size: 13px; padding: 24px; }
.btn { background: var(--accent-primary); border: none; border-radius: 6px; padding: 6px 14px; color: #fff; cursor: pointer; font-size: 12px; }
.btn:disabled { opacity: .5; cursor: wait; }
.btn-s { background: var(--border-default); border: none; border-radius: 6px; padding: 6px 14px; color: var(--text-primary); cursor: pointer; font-size: 12px; }
.btn-s.danger { color: #e74c3c; }
.file-label { display: inline-block; }
</style>
