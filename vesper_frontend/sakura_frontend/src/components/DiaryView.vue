<template>
  <div class="diary-view">
    <!-- 左侧：日历 + 月份导航 -->
    <div class="diary-sidebar">
      <div class="diary-header">
        <h2>日记本</h2>
        <button @click="generate" :disabled="generating" class="gen-btn">{{ generating ? '生成中…' : '写今天日记' }}</button>
      </div>

      <!-- 搜索 -->
      <div class="diary-search">
        <input v-model="searchQuery" placeholder="搜索日记内容..." @input="onSearch" />
      </div>

      <!-- 月份列表 -->
      <div class="month-list">
        <div v-for="month in months" :key="month.key"
          :class="['month-item', { active: selectedMonth === month.key }]"
          @click="selectMonth(month.key)">
          <span class="month-label">{{ month.label }}</span>
          <span class="month-count">{{ month.count }}</span>
        </div>
        <div v-if="!months.length" class="empty-hint">还没有日记</div>
      </div>
    </div>

    <!-- 右侧：日记内容 -->
    <div class="diary-content">
      <div v-if="loading" class="diary-loading">加载中...</div>
      <div v-else-if="!filteredDiaries.length" class="diary-empty">
        {{ searchQuery ? '没有找到匹配的日记' : '这个月还没有日记' }}
      </div>
      <div v-else class="diary-list">
        <div v-for="d in visibleDiaries" :key="d.id" class="diary-entry">
          <div class="entry-header">
            <span class="entry-date">{{ formatDate(d.date) }}</span>
            <span class="entry-mood" v-if="d.mood">{{ d.mood }}</span>
          </div>
          <div class="entry-content">{{ d.content }}</div>
        </div>

        <!-- 加载更多 -->
        <div v-if="filteredDiaries.length > pageSize" class="diary-pagination">
          <button v-if="currentPage > 1" @click="currentPage--" class="page-btn">上一页</button>
          <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
          <button v-if="currentPage < totalPages" @click="currentPage++" class="page-btn">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api'

export default {
  props: { aiName: { type: String, default: '佐仓' } },
  data() {
    return {
      diaries: [],
      loading: true,
      generating: false,
      searchQuery: '',
      selectedMonth: null,
      currentPage: 1,
      pageSize: 10,
    }
  },
  computed: {
    filteredDiaries() {
      let list = this.diaries
      if (this.searchQuery) {
        const q = this.searchQuery.toLowerCase()
        list = list.filter(d => d.content.toLowerCase().includes(q) || (d.mood && d.mood.toLowerCase().includes(q)))
      }
      if (this.selectedMonth) {
        list = list.filter(d => d.date && d.date.startsWith(this.selectedMonth))
      }
      return list
    },
    visibleDiaries() {
      const start = (this.currentPage - 1) * this.pageSize
      return this.filteredDiaries.slice(start, start + this.pageSize)
    },
    totalPages() {
      return Math.max(1, Math.ceil(this.filteredDiaries.length / this.pageSize))
    },
    months() {
      const map = {}
      for (const d of this.diaries) {
        if (!d.date) continue
        const m = d.date.slice(0, 7)
        if (!map[m]) map[m] = { key: m, label: this.formatMonth(m), count: 0 }
        map[m].count++
      }
      return Object.values(map).sort((a, b) => b.key.localeCompare(a.key))
    },
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true
      try {
        const r = await api.get('/memory/diary', { params: { limit: 200 } })
        this.diaries = r.data || []
        // 默认选中最新月份
        if (this.months.length && !this.selectedMonth) {
          this.selectedMonth = this.months[0].key
        }
      } catch (e) { console.error(e) }
      this.loading = false
    },
    selectMonth(m) {
      this.selectedMonth = m
      this.currentPage = 1
    },
    onSearch() {
      this.currentPage = 1
    },
    async generate() {
      this.generating = true
      try {
        await api.post('/memory/diary/generate')
        await this.load()
      } catch (e) { console.error(e) }
      this.generating = false
    },
    formatDate(dateStr) {
      if (!dateStr) return ''
      const parts = dateStr.split('-')
      return `${parts[1]}月${parts[2]}日`
    },
    formatMonth(monthStr) {
      const [y, m] = monthStr.split('-')
      return `${y}年${parseInt(m)}月`
    },
  }
}
</script>

<style scoped>
.diary-view { display: flex; height: 100%; background: var(--surface-app); color: var(--text-primary); }

/* 左侧栏 */
.diary-sidebar { width: 220px; border-right: 1px solid var(--border-default); display: flex; flex-direction: column; flex-shrink: 0; }
.diary-header { padding: 16px; border-bottom: 1px solid var(--border-default); }
.diary-header h2 { font-size: 16px; font-weight: 600; margin-bottom: 10px; }
.gen-btn { width: 100%; background: var(--accent-primary); border: none; color: #fff; border-radius: 6px; padding: 8px; cursor: pointer; font-size: 13px; transition: opacity .15s; }
.gen-btn:disabled { opacity: .5; cursor: not-allowed; }
.diary-search { padding: 12px 16px; border-bottom: 1px solid var(--border-default); }
.diary-search input { width: 100%; padding: 8px 10px; border: 1px solid var(--border-default); border-radius: 6px; background: var(--surface-sidebar); color: var(--text-primary); font-size: 13px; outline: none; box-sizing: border-box; }
.diary-search input:focus { border-color: var(--accent-primary); }
.month-list { flex: 1; overflow-y: auto; padding: 8px 0; }
.month-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; cursor: pointer; transition: all .15s; }
.month-item:hover { background: rgba(255,255,255,.03); }
.month-item.active { background: rgba(255,255,255,.06); color: var(--accent-primary); }
.month-label { font-size: 13px; }
.month-count { font-size: 11px; color: var(--text-secondary); background: rgba(255,255,255,.06); padding: 2px 8px; border-radius: 10px; }
.empty-hint { text-align: center; color: var(--text-secondary); font-size: 13px; padding: 20px; }

/* 右侧内容 */
.diary-content { flex: 1; overflow-y: auto; padding: 20px 28px; }
.diary-loading, .diary-empty { text-align: center; color: var(--text-secondary); font-size: 14px; padding: 40px; }
.diary-list { max-width: 720px; }
.diary-entry { background: var(--surface-sidebar); border-radius: 10px; padding: 16px 20px; margin-bottom: 14px; border: 1px solid var(--border-default); transition: border-color .15s; }
.diary-entry:hover { border-color: rgba(255,255,255,.1); }
.entry-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.entry-date { color: var(--accent-primary); font-size: 14px; font-weight: 600; }
.entry-mood { color: var(--text-secondary); font-size: 12px; background: rgba(255,255,255,.04); padding: 2px 8px; border-radius: 4px; }
.entry-content { color: var(--text-primary); font-size: 14px; line-height: 1.8; white-space: pre-wrap; }

/* 分页 */
.diary-pagination { display: flex; justify-content: center; align-items: center; gap: 16px; padding: 20px 0; }
.page-btn { background: none; border: 1px solid var(--border-default); color: var(--text-secondary); padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all .15s; }
.page-btn:hover { border-color: var(--accent-primary); color: var(--accent-primary); }
.page-info { font-size: 13px; color: var(--text-secondary); }

/* 移动端适配 */
@media (max-width: 768px) {
  .diary-view { flex-direction: column; }
  .diary-sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--border-default);
    max-height: 200px;
  }
  .diary-header { padding: 12px; }
  .diary-header h2 { font-size: 14px; margin-bottom: 8px; }
  .gen-btn { min-height: 44px; font-size: 14px; }
  .diary-search { padding: 8px 12px; }
  .diary-search input { font-size: 16px; padding: 10px; }
  .month-list { max-height: 120px; }
  .month-item { padding: 10px 12px; min-height: 44px; }
  .diary-content { padding: 12px; }
  .diary-entry { padding: 12px; }
  .entry-content { font-size: 14px; }
  .page-btn { min-height: 44px; padding: 8px 16px; }
}
</style>
