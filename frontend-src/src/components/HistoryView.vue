<template>
  <div class="history-view">
    <div class="hv-header">
      <h2>回顾</h2>
      <button class="btn-close" @click="$emit('close')">×</button>
    </div>
    <div class="hv-body">
      <div class="hv-dates">
        <template v-for="(monthDates, month) in groupedDates" :key="month">
          <div class="hv-month-header" @click="toggleMonth(month)">
            {{ month }} ({{ monthDates.length }}) {{ expandedMonths[month] ? '▼' : '▶' }}
          </div>
          <template v-if="expandedMonths[month]">
            <div v-for="d in monthDates" :key="d" :class="['hv-date', { active: d === selectedDate }]" @click="loadDate(d)">
              {{ d.slice(5) }}
            </div>
          </template>
        </template>
        <div v-if="!dates.length" class="hv-empty">暂无聊天记录</div>
      </div>
      <div class="hv-msgs" ref="msgList">
        <div v-if="loading" class="hv-loading">加载中...</div>
        <div v-for="msg in filteredMsgs" :key="msg.id" :class="['hv-msg', msg.role]">
          <div class="hv-msg-meta">
            <span class="hv-msg-role">{{ msg.role === 'user' ? (userName || '我') : (aiName || '夕语') }}</span>
            <span class="hv-msg-time">{{ fmtTime(msg.timestamp) }}</span>
          </div>
          <div class="hv-msg-content">{{ msg.content }}</div>
          <button class="hv-fav-btn" :class="{ fav: isFav(msg.id) }" @click="toggleFav(msg)">{{ isFav(msg.id) ? '★' : '☆' }}</button>
        </div>
        <div v-if="!loading && !filteredMsgs.length && selectedDate" class="hv-empty">该日期无消息</div>
        <div v-if="!selectedDate" class="hv-empty">选择日期查看聊天记录</div>
      </div>
    </div>
    <div class="hv-footer">
      <button :class="{ active: filter === 'all' }" @click="filter = 'all'">全部消息</button>
      <button :class="{ active: filter === 'fav' }" @click="filter = 'fav'">仅收藏</button>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  props: {
    favoriteIds: Set,
    aiName: String,
    userName: String,
  },
  emits: ['close', 'toggle-favorite'],
  data() {
    return {
      dates: [],
      selectedDate: null,
      messages: [],
      loading: false,
      filter: 'all',
      expandedMonths: {},
    }
  },
  computed: {
    filteredMsgs() {
      if (this.filter === 'fav') return this.messages.filter(m => this.favoriteIds?.has(m.id))
      return this.messages
    },
    groupedDates() {
      const groups = {}
      for (const d of this.dates) {
        const month = d.slice(0, 7) // YYYY-MM
        if (!groups[month]) groups[month] = []
        groups[month].push(d)
      }
      return groups
    },
  },
  async mounted() {
    try {
      const res = await api.get('/chat/history/dates')
      const months = res.data?.months || []
      this.dates = months.flatMap(m => (m.dates || []).map(d => d.date))
      // 默认展开最新月份
      if (this.dates.length) {
        const latestMonth = this.dates[0].slice(0, 7)
        this.expandedMonths[latestMonth] = true
      }
    } catch (e) { console.error(e) }
  },
  methods: {
    toggleMonth(month) { this.expandedMonths[month] = !this.expandedMonths[month] },
    async loadDate(d) {
      this.selectedDate = d
      this.loading = true
      try {
        const res = await api.get('/chat/history/date', { params: { date: d } })
        this.messages = res.data?.messages || []
        this.$nextTick(() => { if (this.$refs.msgList) this.$refs.msgList.scrollTop = 0 })
      } catch (e) { console.error(e) }
      this.loading = false
    },
    fmtTime(ts) {
      if (!ts) return ''
      try { const d = new Date(ts); return `${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}` } catch (e) { return '' }
    },
    isFav(id) { return this.favoriteIds?.has(id) },
    toggleFav(msg) { this.$emit('toggle-favorite', msg) },
  }
}
</script>

<style scoped>
.history-view { display: flex; flex-direction: column; height: 100%; background: var(--bg); color: var(--tc); }
.hv-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid var(--border); }
.hv-header h2 { font-size: 16px; font-weight: 600; }
.btn-close { background: none; border: none; color: var(--tc2); font-size: 20px; cursor: pointer; }
.hv-body { display: flex; flex: 1; overflow: hidden; }
.hv-dates { width: 140px; overflow-y: auto; border-right: 1px solid var(--border); padding: 8px 0; }
.hv-month-header { padding: 8px 16px; font-size: 12px; font-weight: 600; color: var(--p); cursor: pointer; user-select: none; }
.hv-month-header:hover { background: rgba(255,255,255,.03); }
.hv-date { padding: 8px 16px; font-size: 13px; cursor: pointer; color: var(--tc2); transition: all .15s; }
.hv-date:hover { color: var(--tc); background: rgba(255,255,255,.03); }
.hv-date.active { color: var(--p); background: rgba(255,255,255,.06); font-weight: 600; }
.hv-msgs { flex: 1; overflow-y: auto; padding: 12px 16px; }
.hv-msg { padding: 10px 12px; margin-bottom: 8px; border-radius: 8px; position: relative; }
.hv-msg.user { background: var(--ub); }
.hv-msg.assistant { background: var(--ab); }
.hv-msg-meta { display: flex; gap: 8px; margin-bottom: 4px; }
.hv-msg-role { font-size: 11px; color: var(--p); font-weight: 600; }
.hv-msg-time { font-size: 11px; color: var(--tc2); }
.hv-msg-content { font-size: 13px; line-height: 1.6; word-break: break-word; }
.hv-fav-btn { position: absolute; top: 8px; right: 10px; background: none; border: none; font-size: 16px; cursor: pointer; color: var(--tc2); transition: color .15s; }
.hv-fav-btn.fav { color: #f0c040; }
.hv-empty { padding: 24px; text-align: center; color: var(--tc2); font-size: 13px; }
.hv-loading { padding: 16px; text-align: center; color: var(--tc2); }
.hv-footer { display: flex; gap: 8px; padding: 10px 16px; border-top: 1px solid var(--border); }
.hv-footer button { padding: 6px 16px; border-radius: 16px; border: 1px solid var(--border); background: var(--bg); color: var(--tc2); font-size: 12px; cursor: pointer; transition: all .15s; }
.hv-footer button.active { background: var(--p); color: #fff; border-color: var(--p); }

/* 移动端适配 */
@media (max-width: 768px) {
  .hv-header { padding: 12px 16px; }
  .hv-header h2 { font-size: 14px; }
  .btn-close { min-width: 44px; min-height: 44px; display: flex; align-items: center; justify-content: center; }
  .hv-body { flex-direction: column; }
  .hv-dates {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--border);
    max-height: 150px;
    overflow-x: auto;
    display: flex;
    flex-wrap: nowrap;
    padding: 0;
  }
  .hv-month-header {
    padding: 10px 12px;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .hv-date {
    padding: 10px 12px;
    white-space: nowrap;
    flex-shrink: 0;
    min-height: 44px;
    display: flex;
    align-items: center;
  }
  .hv-msgs { padding: 8px 12px; }
  .hv-msg { padding: 8px 10px; }
  .hv-msg-content { font-size: 14px; }
  .hv-fav-btn { min-width: 44px; min-height: 44px; display: flex; align-items: center; justify-content: center; }
  .hv-footer { padding: 8px 12px; flex-wrap: wrap; }
  .hv-footer button { min-height: 44px; padding: 8px 16px; font-size: 13px; }
}
</style>
