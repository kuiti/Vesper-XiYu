<template>
  <div class="memory-timeline">
    <div class="tl-header">
      <h3>对话时间线</h3>
      <div class="tl-search">
        <input v-model="searchQuery" placeholder="搜索对话..." @keyup.enter="doSearch" />
        <button @click="doSearch">搜索</button>
      </div>
    </div>

    <div v-if="searchResults.length" class="tl-search-results">
      <div v-for="(r, i) in searchResults" :key="i" class="tl-search-item">
        <span class="tl-sr-topic">{{ r.topic_summary }}</span>
        <span class="tl-sr-time">{{ fmtTime(r.start_time) }}</span>
      </div>
      <button class="tl-clear-search" @click="searchResults = []">清除搜索</button>
    </div>

    <div class="tl-body">
      <div v-if="!timeline.length" class="tl-empty">暂无对话记录</div>
      <div v-for="(group, gi) in groupedTimeline" :key="gi" class="tl-month-group">
        <div class="tl-month-title">{{ group.month }}</div>
        <div v-for="(day, di) in group.days" :key="di" class="tl-day-group">
          <div class="tl-day-header" @click="day.expanded = !day.expanded">
            <span class="tl-day-date">{{ day.date }}</span>
            <span class="tl-day-stars">{{ '★'.repeat(day.stars) }}{{ '☆'.repeat(3 - day.stars) }}</span>
            <span class="tl-day-count">{{ day.episodes.length }} 段对话</span>
            <span class="tl-toggle">{{ day.expanded ? '▼' : '▶' }}</span>
          </div>
          <div v-if="day.expanded" class="tl-episodes">
            <div v-for="(ep, ei) in day.episodes" :key="ei" class="tl-episode">
              <span class="tl-ep-time">{{ fmtTime(ep.start_time) }}</span>
              <span class="tl-ep-topic">{{ ep.topic_summary || '日常聊天' }}</span>
              <span class="tl-ep-importance" :style="{ color: importanceColor(ep.importance) }">
                {{ importanceLabel(ep.importance) }}
              </span>
            </div>
          </div>
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
      timeline: [],
      searchQuery: '',
      searchResults: [],
      days: 14,
    }
  },
  computed: {
    groupedTimeline() {
      const groups = {}
      for (const ep of this.timeline) {
        const date = (ep.start_time || '').slice(0, 10)
        if (!date) continue
        const month = date.slice(0, 7)
        if (!groups[month]) groups[month] = { month, days: {} }
        if (!groups[month].days[date]) {
          const stars = ep.importance >= 0.8 ? 3 : ep.importance >= 0.5 ? 2 : 1
          groups[month].days[date] = { date, stars, episodes: [], expanded: false }
        }
        groups[month].days[date].episodes.push(ep)
      }
      return Object.values(groups).map(g => ({
        ...g,
        days: Object.values(g.days).sort((a, b) => b.date.localeCompare(a.date))
      })).sort((a, b) => b.month.localeCompare(a.month))
    }
  },
  mounted() {
    this.loadTimeline()
  },
  methods: {
    async loadTimeline() {
      try {
        const res = await api.get('/episodes/timeline', { params: { days: this.days } })
        this.timeline = res.data || []
      } catch (e) { console.error(e) }
    },
    async doSearch() {
      if (!this.searchQuery.trim()) return
      try {
        const res = await api.get('/episodes/search', { params: { q: this.searchQuery, limit: 10 } })
        this.searchResults = res.data || []
      } catch (e) { console.error(e) }
    },
    fmtTime(ts) {
      if (!ts) return ''
      return ts.slice(11, 16)
    },
    importanceColor(imp) {
      if (imp >= 0.8) return '#e74c3c'
      if (imp >= 0.5) return '#f39c12'
      return '#95a5a6'
    },
    importanceLabel(imp) {
      if (imp >= 0.8) return '重要'
      if (imp >= 0.5) return '一般'
      return '闲聊'
    }
  }
}
</script>

<style scoped>
.memory-timeline { padding: 16px; color: var(--tc); }
.tl-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.tl-header h3 { margin: 0; font-size: 16px; }
.tl-search { display: flex; gap: 8px; }
.tl-search input { padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--tc); font-size: 13px; width: 200px; }
.tl-search button { padding: 6px 12px; background: var(--p); border: none; color: #fff; border-radius: 6px; cursor: pointer; font-size: 13px; }
.tl-search-results { margin-bottom: 16px; padding: 12px; background: var(--ab); border-radius: 8px; }
.tl-search-item { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }
.tl-sr-topic { color: var(--tc); }
.tl-sr-time { color: var(--tc2); font-size: 12px; }
.tl-clear-search { margin-top: 8px; padding: 4px 8px; background: none; border: 1px solid var(--border); color: var(--tc2); border-radius: 4px; cursor: pointer; font-size: 12px; }
.tl-month-group { margin-bottom: 16px; }
.tl-month-title { font-size: 14px; font-weight: 600; color: var(--p); margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid var(--border); }
.tl-day-group { margin-bottom: 8px; }
.tl-day-header { display: flex; align-items: center; gap: 8px; padding: 8px; background: var(--ab); border-radius: 6px; cursor: pointer; font-size: 13px; }
.tl-day-header:hover { background: rgba(255,255,255,.06); }
.tl-day-date { font-weight: 600; }
.tl-day-stars { color: #f39c12; font-size: 12px; }
.tl-day-count { color: var(--tc2); font-size: 12px; }
.tl-toggle { margin-left: auto; color: var(--tc2); font-size: 10px; }
.tl-episodes { padding: 8px 0 8px 16px; }
.tl-episode { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.tl-ep-time { color: var(--tc2); font-size: 12px; min-width: 40px; }
.tl-ep-topic { flex: 1; }
.tl-ep-importance { font-size: 11px; }
.tl-empty { text-align: center; color: var(--tc2); padding: 32px 0; }
</style>
