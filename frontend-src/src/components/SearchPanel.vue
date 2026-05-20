<template>
  <div class="search-panel">
    <div class="search-box">
      <input 
        v-model="keyword" 
        @keyup.enter="search" 
        placeholder="搜索聊天记录..."
      >
      <button @click="search">🔍</button>
    </div>
    <div class="results" v-if="results.length">
      <div v-for="r in results" :key="r.id" class="result-item">
        <div class="result-meta">{{ r.role }} · {{ formatTime(r.timestamp) }}</div>
        <div class="result-content">{{ r.content }}</div>
      </div>
    </div>
    <div class="empty" v-else-if="searched && !results.length">
      未找到相关记录
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  data() {
    return {
      keyword: '',
      results: [],
      searched: false
    }
  },
  methods: {
    async search() {
      if (!this.keyword.trim()) return
      this.searched = true
      try {
        const res = await api.get('/search/chat', {
          params: { q: this.keyword, limit: 30 }
        })
        this.results = res.data
      } catch (err) {
        console.error('搜索失败', err)
      }
    },
    formatTime(ts) {
      if (!ts) return ''
      return ts.slice(0, 16).replace('T', ' ')
    }
  }
}
</script>

<style scoped>
.search-panel {
  padding: 10px;
}
.search-box {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.search-box input {
  flex: 1;
  padding: 6px;
  border-radius: 6px;
  border: 1px solid #2c3e50;
  background: #1a1a2e;
  color: white;
}
.search-box button {
  background: #4e89ae;
  border: none;
  border-radius: 6px;
  color: white;
  cursor: pointer;
  width: 32px;
}
.results {
  max-height: 400px;
  overflow-y: auto;
}
.result-item {
  background: #16213e;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
}
.result-meta {
  font-size: 11px;
  color: #7f8c8d;
  margin-bottom: 4px;
}
.result-content {
  font-size: 13px;
  color: #ecf0f1;
  word-break: break-all;
}
.empty {
  color: #7f8c8d;
  text-align: center;
  padding: 20px;
  font-size: 13px;
}
</style>