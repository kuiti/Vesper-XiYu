<template>
  <div class="diary-panel">
    <div class="diary-header">
      <span>日记本</span>
      <button @click="generate" :disabled="generating" class="gen-btn">{{ generating ? '生成中…' : '生成今天日记' }}</button>
    </div>
    <div class="items">
      <div v-for="d in visibleDiaries" :key="d.id" class="diary-item">
        <div class="diary-date">{{ d.date }}</div>
        <div class="diary-mood" v-if="d.mood">{{ d.mood }}</div>
        <div class="diary-content">{{ d.content }}</div>
      </div>
      <button v-if="diaries.length > pageSize" class="diary-more" @click="showAll = !showAll">
        {{ showAll ? '收起' : '展开全部 ' + diaries.length + ' 篇' }}
      </button>
      <div v-if="!diaries.length" class="empty">还没有日记。点击"生成今天日记"让{{ aiName }}写一篇，或者等待晚上 11 点自动生成</div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  props: { aiName: { type: String, default: '佐仓' } },
  data() { return { diaries: [], generating: false, showAll: false, pageSize: 5 } },
  computed: { visibleDiaries() { return this.showAll ? this.diaries : this.diaries.slice(0, this.pageSize) } },
  mounted() { this.load() },
  methods: {
    async load() { try { const r = await api.get('/memory/diary', { params: { limit: 50 } }); this.diaries = r.data || [] } catch (e) { console.error(e) } },
    async generate() {
      this.generating = true
      try { await api.post('/memory/diary/generate'); await this.load() } catch (e) { console.error(e) }
      this.generating = false
    }
  }
}
</script>

<style scoped>
.diary-panel { padding: 10px; }
.diary-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; color: var(--tc); font-size: 15px; font-weight: 600; }
.gen-btn { background: var(--p); border: none; color: #fff; border-radius: 6px; padding: 6px 14px; cursor: pointer; font-size: 13px; }
.gen-btn:disabled { opacity: .5; cursor: not-allowed; }
.diary-item { background: var(--sb); border-radius: 8px; padding: 12px; margin-bottom: 10px; }
.diary-date { color: var(--p); font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.diary-mood { color: var(--tc2); font-size: 12px; margin-bottom: 6px; }
.diary-content { color: var(--tc); font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
.diary-more { background: none; border: 1px solid rgba(255,255,255,.1); color: var(--tc2); cursor: pointer; font-size: 11px; padding: 4px 12px; border-radius: 4px; margin-top: 4px; display: block; width: 100%; }
.diary-more:hover { border-color: var(--p); color: var(--p); }
.empty { text-align: center; color: var(--tc2); font-size: 13px; padding: 20px; }
</style>
