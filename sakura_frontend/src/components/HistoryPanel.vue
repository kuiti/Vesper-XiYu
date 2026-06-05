<template>
  <div class="history-panel">
    <div v-if="!months.length" class="empty">暂无历史消息</div>
    <div v-for="month in months" :key="month.month" class="month-group">
      <div class="month-head">{{ formatMonth(month.month) }}</div>
      <div class="date-list">
        <div v-for="d in month.dates" :key="d.date" class="date-row" @click="loadDate(d.date)">
          <span class="date-label">{{ formatDate(d.date) }}</span>
          <span class="date-count">{{ d.count }} 条</span>
        </div>
      </div>
    </div>
    <div v-if="dateMessages.length" class="date-detail">
      <div class="detail-head">
        <button @click="dateMessages=[]">← 返回</button>
        <span>{{ viewingDate }}</span>
      </div>
      <div class="detail-list">
        <div v-for="(msg, idx) in dateMessages" :key="idx" :class="['dmsg', msg.role]">
          <div class="dmsg-time">{{ formatTime(msg.timestamp) }}</div>
          <div class="dmsg-text">{{ msg.content }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  data() {
    return {
      months: [],
      dateMessages: [],
      viewingDate: ''
    }
  },
  mounted() {
    this.loadDates()
  },
  beforeUnmount() {
    if (this._loadAbort) { this._loadAbort.abort(); this._loadAbort = null }
  },
  methods: {
    async loadDates() {
      try {
        const res = await api.get('/chat/history/dates')
        this.months = res.data?.months || []
      } catch (err) {
        console.error('加载日期失败', err)
      }
    },
    async loadDate(date) {
      try {
        if (this._loadAbort) this._loadAbort.abort()
        this._loadAbort = new AbortController()
        const res = await api.get(`/chat/history/date?date=${encodeURIComponent(date)}`, { signal: this._loadAbort.signal })
        this.dateMessages = res.data?.messages || []
        this.viewingDate = date
      } catch (err) {
        if (err?.name !== 'CanceledError' && err?.code !== 'ERR_CANCELED') console.error('加载消息失败', err)
      }
    },
    formatMonth(m) {
      const [y, mo] = m.split('-')
      return `${y}年${parseInt(mo)}月`
    },
    formatDate(d) {
      const parts = d.split('-')
      return `${parseInt(parts[1])}月${parseInt(parts[2])}日`
    },
    formatTime(ts) {
      try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) } catch { return '' }
    }
  }
}
</script>

<style scoped>
.history-panel { padding: 10px; color: #ecf0f1; max-height: 70vh; overflow-y: auto; }
.empty { color: #7f8c8d; text-align: center; padding: 20px; font-size: 13px; }
.month-group { margin-bottom: 16px; }
.month-head { font-size: 13px; color: var(--p); font-weight: 600; padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,.06); margin-bottom: 6px; }
.date-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; border-radius: 6px; cursor: pointer; font-size: 13px; transition: background .15s; }
.date-row:hover { background: rgba(255,255,255,.05); }
.date-label { color: #ccc; }
.date-count { font-size: 11px; color: #7f8c8d; }
.date-detail { margin-top: 8px; }
.detail-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.detail-head button { background: none; border: none; color: var(--p); cursor: pointer; font-size: 13px; }
.detail-head span { font-size: 13px; color: #ccc; }
.detail-list { display: flex; flex-direction: column; gap: 10px; }
.dmsg { padding: 8px 10px; border-radius: 8px; }
.dmsg.user { background: rgba(43,82,120,.3); }
.dmsg.assistant { background: rgba(30,38,50,.5); }
.dmsg-time { font-size: 10px; color: #7f8c8d; margin-bottom: 3px; }
.dmsg-text { font-size: 13px; word-break: break-word; white-space: pre-wrap; }
</style>
