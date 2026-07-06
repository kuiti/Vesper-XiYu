<template>
  <div class="character-select">
    <div class="cs-header">
      <h3>角色管理</h3>
      <div class="cs-actions">
        <button class="cs-btn" @click="showImport = !showImport">导入</button>
        <button class="cs-btn cs-btn-add" @click="showCreate = !showCreate">+</button>
      </div>
    </div>

    <!-- 导入面板 -->
    <div v-if="showImport" class="cs-import">
      <div class="cs-import-tabs">
        <button :class="{active: importTab === 'json'}" @click="importTab = 'json'">JSON</button>
        <button :class="{active: importTab === 'png'}" @click="importTab = 'png'">PNG</button>
      </div>
      <div v-if="importTab === 'json'">
        <textarea v-model="importJson" placeholder="粘贴角色卡 JSON..." class="cs-textarea"></textarea>
        <button class="cs-btn" @click="doImportJson">导入 JSON</button>
      </div>
      <div v-else>
        <input type="file" accept=".png" @change="doImportPng" ref="pngInput" />
      </div>
    </div>

    <!-- 创建面板 -->
    <div v-if="showCreate" class="cs-create">
      <input v-model="newName" placeholder="角色名称" class="cs-input" />
      <textarea v-model="newDesc" placeholder="角色描述..." class="cs-textarea"></textarea>
      <button class="cs-btn" @click="doCreate" :disabled="!newName">创建</button>
    </div>

    <!-- 角色列表 -->
    <div class="cs-list">
      <div v-for="c in characters" :key="c.id"
        :class="['cs-card', { active: c.is_active }]"
        @click="activateCharacter(c.id)">
        <div class="cs-card-avatar">
          <img v-if="c.avatar" :src="avatarUrl(c.avatar)" />
          <div v-else class="cs-avatar-placeholder">{{ (c.name || '?')[0] }}</div>
        </div>
        <div class="cs-card-info">
          <div class="cs-card-name">{{ c.name }}</div>
          <div class="cs-card-desc">{{ (c.description || '').slice(0, 60) }}</div>
        </div>
        <div class="cs-card-actions">
          <button v-if="!c.is_active" class="cs-activate-btn" @click.stop="activateCharacter(c.id)">使用</button>
          <span v-else class="cs-active-badge">当前</span>
          <button class="cs-delete-btn" @click.stop="deleteCharacter(c.id)">×</button>
        </div>
      </div>
      <div v-if="!characters.length" class="cs-empty">暂无角色，点击"导入"或"+"创建</div>
    </div>

    <div v-if="msg" class="cs-msg">{{ msg }}</div>
  </div>
</template>

<script>
import api from '../api'

export default {
  data() {
    return {
      characters: [],
      showImport: false,
      showCreate: false,
      importTab: 'json',
      importJson: '',
      newName: '',
      newDesc: '',
      msg: '',
    }
  },
  mounted() {
    this.loadCharacters()
  },
  methods: {
    async loadCharacters() {
      try {
        const res = await api.get('/characters/')
        this.characters = res.data.characters || []
      } catch (e) { console.error(e) }
    },
    async activateCharacter(id) {
      try {
        await api.post(`/characters/activate/${id}`)
        await this.loadCharacters()
        this.msg = '角色已切换'
        setTimeout(() => this.msg = '', 2000)
      } catch (e) { this.msg = '切换失败'; console.error(e) }
    },
    async deleteCharacter(id) {
      if (!confirm('确定删除此角色？')) return
      try {
        await api.delete(`/characters/${id}`)
        await this.loadCharacters()
      } catch (e) { console.error(e) }
    },
    async doImportJson() {
      if (!this.importJson.trim()) return
      try {
        const data = JSON.parse(this.importJson)
        await api.post('/characters/import/json', data)
        this.importJson = ''
        this.showImport = false
        await this.loadCharacters()
        this.msg = '导入成功'
        setTimeout(() => this.msg = '', 2000)
      } catch (e) { this.msg = '导入失败：JSON 格式错误'; console.error(e) }
    },
    async doImportPng(e) {
      const file = e.target.files[0]
      if (!file) return
      const form = new FormData()
      form.append('file', file)
      try {
        await api.post('/characters/import/png', form)
        this.showImport = false
        await this.loadCharacters()
        this.msg = '导入成功'
        setTimeout(() => this.msg = '', 2000)
      } catch (e) { this.msg = '导入失败：PNG 解析错误'; console.error(e) }
    },
    async doCreate() {
      if (!this.newName.trim()) return
      try {
        await api.post('/characters/', { name: this.newName, description: this.newDesc })
        this.newName = ''
        this.newDesc = ''
        this.showCreate = false
        await this.loadCharacters()
      } catch (e) { console.error(e) }
    },
    avatarUrl(path) {
      if (!path) return ''
      if (path.startsWith('http') || path.startsWith('data:')) return path
      return `/avatars/${path}`
    }
  }
}
</script>

<style scoped>
.character-select { padding: 16px; color: var(--tc); }
.cs-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.cs-header h3 { margin: 0; font-size: 16px; }
.cs-actions { display: flex; gap: 8px; }
.cs-btn { padding: 6px 12px; background: var(--p); border: none; color: #fff; border-radius: 6px; cursor: pointer; font-size: 13px; }
.cs-btn:disabled { opacity: .4; cursor: not-allowed; }
.cs-btn-add { width: 30px; height: 30px; padding: 0; border-radius: 50%; font-size: 16px; display: flex; align-items: center; justify-content: center; }
.cs-import, .cs-create { margin-bottom: 12px; padding: 12px; background: var(--ab); border-radius: 8px; display: flex; flex-direction: column; gap: 8px; }
.cs-import-tabs { display: flex; gap: 4px; margin-bottom: 8px; }
.cs-import-tabs button { padding: 4px 12px; border: 1px solid var(--border); background: none; color: var(--tc2); border-radius: 4px; cursor: pointer; font-size: 12px; }
.cs-import-tabs button.active { background: var(--p); color: #fff; border-color: var(--p); }
.cs-input { padding: 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--tc); font-size: 13px; }
.cs-textarea { padding: 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--tc); font-size: 13px; min-height: 80px; resize: vertical; font-family: inherit; }
.cs-list { display: flex; flex-direction: column; gap: 8px; }
.cs-card { display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--ab); border-radius: 8px; cursor: pointer; border: 2px solid transparent; transition: all .15s; }
.cs-card:hover { border-color: var(--p); }
.cs-card.active { border-color: var(--p); background: rgba(var(--p-rgb, 106,159,216), .1); }
.cs-card-avatar { width: 40px; height: 40px; border-radius: 8px; overflow: hidden; flex-shrink: 0; }
.cs-card-avatar img { width: 100%; height: 100%; object-fit: cover; }
.cs-avatar-placeholder { width: 100%; height: 100%; background: var(--p); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 600; }
.cs-card-info { flex: 1; min-width: 0; }
.cs-card-name { font-size: 14px; font-weight: 600; }
.cs-card-desc { font-size: 12px; color: var(--tc2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-card-actions { display: flex; align-items: center; gap: 8px; }
.cs-activate-btn { padding: 4px 10px; background: var(--p); border: none; color: #fff; border-radius: 4px; cursor: pointer; font-size: 12px; }
.cs-active-badge { padding: 4px 10px; background: rgba(46,160,67,.2); color: #2ea043; border-radius: 4px; font-size: 12px; }
.cs-delete-btn { background: none; border: none; color: var(--tc2); cursor: pointer; font-size: 16px; opacity: .4; }
.cs-delete-btn:hover { opacity: 1; color: #e74c3c; }
.cs-empty { text-align: center; color: var(--tc2); padding: 24px 0; font-size: 13px; }
.cs-msg { margin-top: 8px; text-align: center; font-size: 12px; color: var(--p); }
</style>
