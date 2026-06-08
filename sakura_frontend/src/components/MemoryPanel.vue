<template>
  <div class="memory-panel">
    <div class="add-memory">
      <input v-model="newKey" placeholder="键名" />
      <input v-model="newValue" placeholder="值" />
      <button @click="addMemory">+</button>
    </div>
    <div class="items">
      <div v-for="(value, key) in memories" :key="key" class="item">
        <span class="key">{{ key }}</span>
        <span class="value">{{ value }}</span>
        <button @click="deleteMemory(key)" class="del-btn">删除</button>
      </div>
      <div v-if="Object.keys(memories).length === 0" class="empty">暂无手动记忆</div>
    </div>
    <div class="summary-section">
      <hr />
      <h4>📝 长对话摘要</h4>
      <div class="summary-text">{{ summary || '暂无摘要' }}</div>
      <div class="keypoints">
        <span v-for="(kp, i) in keypoints" :key="i" class="keypoint">{{ kp }}</span>
      </div>
      <button @click="resetSummary" :disabled="resetting">{{ resetting ? '重置中...' : '重置摘要记忆' }}</button>
    </div>
  </div>
</template>

<script>
import api from '../api.js'
import { showConfirm, alert as showAlert } from '../utils/dialog.js'

export default {
  data() {
    return {
      memories: {},
      newKey: '',
      newValue: '',
      summary: '',
      keypoints: [],
      resetting: false
    }
  },
  mounted() {
    this.loadMemory()
    this.loadSummary()
  },
  methods: {
    async loadMemory() {
      try {
        const res = await api.get('/memory/')
        this.memories = (res.data && typeof res.data === 'object' && !Array.isArray(res.data)) ? res.data : {}
      } catch (err) { console.error(err) }
    },
    async addMemory() {
      if (!this.newKey || !this.newValue) return
      try {
        await api.post('/memory/', { key: this.newKey, value: this.newValue })
        this.newKey = ''
        this.newValue = ''
        await this.loadMemory()
      } catch (err) { console.error(err) }
    },
    async deleteMemory(key) {
      if (!await showConfirm({ content: `删除记忆 "${key}"？` })) return
      try {
        await api.delete(`/memory/${encodeURIComponent(key)}`)
        await this.loadMemory()
      } catch (err) { console.error(err) }
    },
    async loadSummary() {
      try {
        const res = await api.get('/summary/active')
        const d = res.data || {}
        this.summary = d.summary || ''
        this.keypoints = d.keypoints || []
      } catch (err) { console.error(err) }
    },
    async resetSummary() {
      if (!await showConfirm({ content: '确定要重置摘要记忆？此操作不可撤销。' })) return
      this.resetting = true
      try {
        await api.post('/summary/reset')
        await this.loadSummary()
      } catch (err) { console.error(err) }
      finally { this.resetting = false }
    }
  }
}
</script>

<style scoped>
.memory-panel { padding: 8px; }
.add-memory { display: flex; gap: 8px; margin-bottom: 12px; }
.add-memory input { flex: 1; padding: 6px; border-radius: 6px; background: var(--bg); color: var(--tc); border: 1px solid var(--border); }
.add-memory button { background: var(--p); border: none; color: #fff; border-radius: 6px; cursor: pointer; padding: 0 12px; }
.item { display: flex; justify-content: space-between; align-items: center; padding: 6px; background: var(--sb); border-radius: 6px; margin-bottom: 6px; }
.item .key { font-weight: bold; color: var(--p); width: 80px; }
.item .value { flex: 1; color: var(--tc); }
.item button { background: none; border: none; color: #e74c3c; cursor: pointer; }
.empty, .summary-text { text-align: center; color: var(--tc2); font-size: 13px; padding: 12px; }
.summary-section { margin-top: 16px; }
.keypoints { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
.keypoint { background: var(--border); padding: 4px 8px; border-radius: 12px; font-size: 12px; color: var(--tc2); }
</style>