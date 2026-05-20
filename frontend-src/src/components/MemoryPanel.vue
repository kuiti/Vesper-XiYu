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
        <button @click="deleteMemory(key)">🗑️</button>
      </div>
      <div v-if="Object.keys(memories).length === 0" class="empty">暂无手动记忆</div>
    </div>
    <div class="summary-section">
      <hr />
      <h4>📝 长对话摘要</h4>
      <div class="summary-text">{{ summary || '暂无摘要' }}</div>
      <div class="keypoints">
        <span v-for="kp in keypoints" :key="kp" class="keypoint">{{ kp }}</span>
      </div>
      <button @click="resetSummary">重置摘要记忆</button>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  data() {
    return {
      memories: {},
      newKey: '',
      newValue: '',
      summary: '',
      keypoints: []
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
        this.memories = res.data
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
      if (!confirm(`删除记忆 "${key}"？`)) return
      try {
        await api.delete(`/memory/${key}`)
        await this.loadMemory()
      } catch (err) { console.error(err) }
    },
    async loadSummary() {
      try {
        const res = await api.get('/summary/active')
        this.summary = res.data.summary
        this.keypoints = res.data.keypoints || []
      } catch (err) { console.error(err) }
    },
    async resetSummary() {
      if (!confirm('确定要重置摘要记忆？此操作不可撤销。')) return
      try {
        await api.post('/summary/reset')
        await this.loadSummary()
      } catch (err) { console.error(err) }
    }
  }
}
</script>

<style scoped>
.memory-panel { padding: 8px; }
.add-memory { display: flex; gap: 8px; margin-bottom: 12px; }
.add-memory input { flex: 1; padding: 6px; border-radius: 6px; background: #1a1a2e; color: white; border: 1px solid #2c3e50; }
.add-memory button { background: #4e89ae; border: none; color: white; border-radius: 6px; cursor: pointer; padding: 0 12px; }
.item { display: flex; justify-content: space-between; align-items: center; padding: 6px; background: #16213e; border-radius: 6px; margin-bottom: 6px; }
.item .key { font-weight: bold; color: #4e89ae; width: 80px; }
.item .value { flex: 1; color: white; }
.item button { background: none; border: none; color: #e74c3c; cursor: pointer; }
.empty, .summary-text { text-align: center; color: #7f8c8d; font-size: 13px; padding: 12px; }
.summary-section { margin-top: 16px; }
.keypoints { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
.keypoint { background: #2c3e50; padding: 4px 8px; border-radius: 12px; font-size: 12px; color: #bdc3c7; }
</style>