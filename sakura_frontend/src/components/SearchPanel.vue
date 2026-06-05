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
        <div class="result-content" v-html="safeHtml(r.snippet || r.content)"></div>
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
      if (this._abort) this._abort.abort()
      this._abort = new AbortController()
      try {
        const res = await api.get('/search/chat', {
          params: { q: this.keyword, limit: 30 },
          signal: this._abort.signal
        })
        this.results = Array.isArray(res.data) ? res.data : (res.data?.results || [])
      } catch (err) {
        if (err?.name !== 'CanceledError' && err?.code !== 'ERR_CANCELED') {
          this.results = []
          console.error('搜索失败', err)
        }
      }
    },
    formatTime(ts) {
      if (!ts) return ''
      const s = String(ts)
      return s.slice(0, 16).replace('T', ' ')
    },
    safeHtml(raw) {
      if (!raw) return ''
      let escaped = raw.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      escaped = escaped.replace(/&lt;mark&gt;/g, '<mark>').replace(/&lt;\/mark&gt;/g, '</mark>')
      return escaped
    }
  }
}
</script>

<style scoped>
.result-content :deep(mark) { background: var(--p, #5390d4); color: #fff; padding: 0 2px; border-radius: 2px; }
.search-panel { padding: 10px; }
.search-box { display: flex; gap: 8px; margin-bottom: 12px; }
.search-box input { flex: 1; padding: 6px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg); color: var(--tc); }
.search-box button { background: var(--p); border: none; border-radius: 6px; color: #fff; cursor: pointer; width: 32px; }
.results { max-height: 400px; overflow-y: auto; }
.result-item { background: var(--sb); border-radius: 6px; padding: 8px; margin-bottom: 8px; }
.result-meta { font-size: 11px; color: var(--tc2); margin-bottom: 4px; }
.result-content { font-size: 13px; color: var(--tc); word-break: break-all; }
.empty { color: var(--tc2); text-align: center; padding: 20px; font-size: 13px; }
</style>