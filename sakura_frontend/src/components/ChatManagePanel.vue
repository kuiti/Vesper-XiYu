<template>
  <div class="chat-manage">
    <div class="section">
      <h4>快捷删除</h4>
      <div class="quick-buttons">
        <button @click="quickDelete('30min')">半小时</button>
        <button @click="quickDelete('60min')">一小时</button>
        <button @click="quickDelete('today')">今天</button>
        <button @click="quickDelete('yesterday')">昨天</button>
        <button @click="quickDelete('3days')">最近3天</button>
        <button @click="quickDelete('7days')">最近7天</button>
        <button @click="quickDelete('14days')">最近14天</button>
        <button @click="quickDelete('30days')">最近30天</button>
        <button @click="quickDelete('60days')">最近60天</button>
        <button @click="quickDelete('90days')">最近90天</button>
        <button @click="quickDelete('180days')">最近半年</button>
        <button @click="quickDelete('365days')">最近一年</button>
        <button @click="deleteAll" class="danger-btn">清除全部</button>
      </div>
    </div>

    <div class="section">
      <h4>自定义日期范围</h4>
      <div class="date-range">
        <span class="range-label">从</span>
        <div class="date-selects">
          <select v-model.number="startYear"><option v-for="y in years" :key="y" :value="y">{{ y }}年</option></select>
          <select v-model.number="startMonth" @change="fixStartDay"><option v-for="m in 12" :key="m" :value="m">{{ m }}月</option></select>
          <select v-model.number="startDay"><option v-for="d in startMaxDay" :key="d" :value="d">{{ d }}日</option></select>
        </div>
        <span class="range-label">至</span>
        <div class="date-selects">
          <select v-model.number="endYear"><option v-for="y in years" :key="y" :value="y">{{ y }}年</option></select>
          <select v-model.number="endMonth" @change="fixEndDay"><option v-for="m in 12" :key="m" :value="m">{{ m }}月</option></select>
          <select v-model.number="endDay"><option v-for="d in endMaxDay" :key="d" :value="d">{{ d }}日</option></select>
        </div>
        <button @click="deleteRange" :disabled="!dateValid" :title="dateErrorMsg">删除</button>
      </div>
      <div v-if="dateErrorMsg" class="date-error">{{ dateErrorMsg }}</div>
    </div>

    <div class="section">
      <h4>自动清理</h4>
      <div class="auto-cleanup">
        <input type="number" v-model.number="cleanupDays" min="7" max="365">
        <span>天前的记录</span>
        <button @click="saveCleanupSettings">保存</button>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'
import { showConfirm, alert as showAlert } from '../utils/dialog.js'

export default {
  data() {
    return {
      startYear: new Date().getFullYear(),
      startMonth: new Date().getMonth() + 1,
      startDay: new Date().getDate(),
      endYear: new Date().getFullYear(),
      endMonth: new Date().getMonth() + 1,
      endDay: new Date().getDate(),
      cleanupDays: 30,
      dateError: '' // kept for compatibility, but dateErrorMsg is the computed version
    }
  },
  computed: {
    years() {
      const y = new Date().getFullYear()
      const arr = []
      for (let i = y - 5; i <= y; i++) arr.push(i)
      return arr
    },
    startMaxDay() { return new Date(this.startYear, this.startMonth, 0).getDate() },
    endMaxDay() { return new Date(this.endYear, this.endMonth, 0).getDate() },
    dateValid() {
      const d1 = new Date(this.startYear, this.startMonth - 1, this.startDay)
      const d2 = new Date(this.endYear, this.endMonth - 1, this.endDay)
      if (d1 > d2) return false
      if (d2 > new Date()) return false
      return true
    },
    dateErrorMsg() {
      const d1 = new Date(this.startYear, this.startMonth - 1, this.startDay)
      const d2 = new Date(this.endYear, this.endMonth - 1, this.endDay)
      if (d1 > d2) return '开始日期不能晚于结束日期'
      if (d2 > new Date()) return '结束日期不能超过今天'
      return ''
    }
  },
  mounted() { this.loadCleanupSettings() },
  methods: {
    fixStartDay() { if (this.startDay > this.startMaxDay) this.startDay = this.startMaxDay },
    fixEndDay() { if (this.endDay > this.endMaxDay) this.endDay = this.endMaxDay },
    _fmt(y, m, d) { return `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}` },
    async quickDelete(type) {
      const labels = { '30min': '半小时', '60min': '一小时', today: '今天', yesterday: '昨天', '3days': '最近3天', '7days': '最近7天', '14days': '最近14天', '30days': '最近30天', '60days': '最近60天', '90days': '最近90天', '180days': '最近半年', '365days': '最近一年' }
      if (!await showConfirm({ content: `确定删除${labels[type]}的记录吗？此操作同时清除AI记忆。` })) return
      try {
        if (type === '30min') { await api.delete('/chat/manage/recent/30') }
        else if (type === '60min') { await api.delete('/chat/manage/recent/60') }
        else if (type === 'today') { const d = new Date(); const t = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; await api.delete('/chat/manage/range', { data: { start: t + 'T00:00:00', end: t + 'T23:59:59' } }) }
        else if (type === 'yesterday') { const d = new Date(Date.now() - 86400000); const y = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; await api.delete('/chat/manage/range', { data: { start: y + 'T00:00:00', end: y + 'T23:59:59' } }) }
        else { const days = parseInt(type.replace('days','')); await api.delete(`/chat/manage/older-than/${days}`) }
        this.$emit('changed')
      } catch (err) { console.error(err); showAlert('删除失败') }
    },
    async deleteAll() {
      if (!await showConfirm({ content: '确定清除全部聊天记录和AI记忆？此操作不可恢复！' })) return
      try { await api.delete('/chat/manage/all'); this.$emit('changed') } catch (err) { console.error(err); showAlert('清除失败') }
    },
    async deleteRange() {
      if (!this.dateValid) return
      const start = this._fmt(this.startYear, this.startMonth, this.startDay)
      const end = this._fmt(this.endYear, this.endMonth, this.endDay)
      if (!await showConfirm({ content: `确定删除 ${start} 至 ${end} 的聊天记录和AI记忆吗？` })) return
      try { await api.delete('/chat/manage/range', { data: { start, end } }); this.$emit('changed'); showAlert('已删除') } catch (err) { console.error(err); showAlert('删除失败') }
    },
    async loadCleanupSettings() { try { const res = await api.get('/chat/manage/cleanup-settings'); const d = res.data.auto_cleanup_days; this.cleanupDays = (typeof d === 'number' && d >= 7 && d <= 365) ? d : 30 } catch (err) {} },
    async saveCleanupSettings() { try { await api.post('/chat/manage/cleanup-settings', { days: this.cleanupDays }); showAlert('自动清理设置已保存') } catch (err) { console.error(err) } }
  }
}
</script>

<style scoped>
.chat-manage { padding: 10px; }
.section { margin-bottom: 20px; }
.section h4 { margin: 0 0 10px 0; color: var(--p); font-size: 14px; }
.quick-buttons { display: flex; flex-wrap: wrap; gap: 8px; }
.quick-buttons button { background: var(--sb); border: 1px solid var(--border); border-radius: 6px; padding: 6px 12px; color: var(--tc); cursor: pointer; font-size: 12px; transition: background .15s; }
.quick-buttons button:hover { background: var(--p); color: #fff; }
.date-range { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.range-label { color: var(--tc2); font-size: 13px; }
.date-selects { display: flex; gap: 4px; }
.date-selects select { padding: 6px 4px; border-radius: 6px; background: var(--bg); color: var(--tc); border: 1px solid var(--border); font-size: 13px; }
.date-range > button { background: var(--p); border: none; border-radius: 6px; padding: 6px 14px; color: #fff; cursor: pointer; }
.date-range > button:disabled { opacity: .4; cursor: not-allowed; }
.date-error { color: #e74c3c; font-size: 11px; margin-top: 6px; }
.danger-btn { background: #e74c3c !important; color: #fff !important; border-color: #e74c3c !important; }
.danger-btn:hover { background: #c0392b !important; }
.auto-cleanup { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.auto-cleanup input { width: 80px; padding: 6px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg); color: var(--tc); }
.auto-cleanup span { color: var(--tc2); font-size: 13px; }
.auto-cleanup button { background: var(--p); border: none; border-radius: 6px; padding: 6px 14px; color: #fff; cursor: pointer; }
</style>
