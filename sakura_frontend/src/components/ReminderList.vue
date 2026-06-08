<template>
  <div class="reminder-list">
    <div class="add-item">
      <input v-model="newContent" placeholder="提醒内容" />
      <div class="time-selects">
        <select v-model.number="selYear"><option v-for="y in years" :key="y" :value="y">{{ y }}年</option></select>
        <select v-model.number="selMonth" @change="fixDay"><option v-for="m in 12" :key="m" :value="m">{{ m }}月</option></select>
        <select v-model.number="selDay"><option v-for="d in maxDay" :key="d" :value="d">{{ d }}日</option></select>
        <select v-model.number="selHour"><option v-for="h in 24" :key="h-1" :value="h-1">{{ String(h-1).padStart(2,'0') }}时</option></select>
        <select v-model.number="selMin"><option v-for="m in mins" :key="m" :value="m">{{ String(m).padStart(2,'0') }}分</option></select>
      </div>
      <select v-model="newLevel" class="lvl-sel">
        <option v-for="l in levels" :key="l.level" :value="l.level">{{ l.name }}</option>
      </select>
      <button @click="addReminder">+</button>
    </div>
    <div class="items">
      <div v-for="r in reminders" :key="r.id" :class="['item', { done: r.done }]" :data-level="r.level">
        <div>
          <strong>{{ r.content }}</strong>
          <div class="meta">目标: {{ formatTime(r.target_time) }} | 等级: {{ getLevelName(r.level) }}</div>
        </div>
        <div class="actions">
          <button v-if="!r.done" class="btn-done" @click="markDone(r.id)" title="标记完成">✓</button>
          <button @click="deleteReminder(r.id)" class="del-btn">删除</button>
        </div>
      </div>
      <div v-if="!reminders.length" class="empty">还没提醒。输入内容和时间就能创建一个</div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'
import { showConfirm, alert as showAlert } from '../utils/dialog.js'

const LEVELS = [
  { level: 7, name: '强制', advance_minutes: 0 },
  { level: 6, name: '重要', advance_minutes: 21*24*60 },
  { level: 5, name: '考试', advance_minutes: 14*24*60 },
  { level: 4, name: '待办', advance_minutes: 5*24*60 },
  { level: 3, name: '计划', advance_minutes: 2*24*60 },
  { level: 2, name: '日常', advance_minutes: 5*60 },
  { level: 1, name: '喝水', advance_minutes: 30 }
]

export default {
  inject: { showConfirm: { default: () => async (msg) => await showConfirm({ content: msg }) } },
  data() {
    const now = new Date()
    return {
      reminders: [],
      newContent: '',
      selYear: now.getFullYear(),
      selMonth: now.getMonth() + 1,
      selDay: now.getDate(),
      selHour: now.getHours(),
      selMin: 0,
      newLevel: 4,
      levels: LEVELS
    }
  },
  computed: {
    years() {
      const y = new Date().getFullYear()
      const arr = []
      for (let i = y - 1; i <= y + 10; i++) arr.push(i)
      return arr
    },
    maxDay() {
      return new Date(this.selYear, this.selMonth, 0).getDate()
    },
    mins() {
      const arr = []
      for (let i = 0; i < 60; i += 5) arr.push(i)
      return arr
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      try { const res = await api.get('/reminders/'); this.reminders = res.data } catch (err) { console.error(err) }
    },
    fixDay() {
      if (this.selDay > this.maxDay) this.selDay = this.maxDay
    },
    formatTime(iso) {
      if (!iso) return ''
      return new Date(iso).toLocaleString()
    },
    getLevelName(level) {
      const l = LEVELS.find(l => l.level === level)
      return l ? l.name : '未知'
    },
    async addReminder() {
      if (!this.newContent) return
      try {
        const mm = String(this.selMonth).padStart(2, '0')
        const dd = String(this.selDay).padStart(2, '0')
        const hh = String(this.selHour).padStart(2, '0')
        const mi = String(this.selMin).padStart(2, '0')
        const targetTime = `${this.selYear}-${mm}-${dd}T${hh}:${mi}:00`
        await api.post('/reminders/', { content: this.newContent, target_time: targetTime, level: this.newLevel })
        this.newContent = ''
        await this.load()
      } catch (err) { console.error(err) }
    },
    async markDone(id) {
      try { await api.patch(`/reminders/${id}/done`); await this.load() } catch (err) { console.error(err) }
    },
    async deleteReminder(id) {
      if (!await this.showConfirm('删除此提醒？')) return
      try { await api.delete(`/reminders/${id}`); await this.load() } catch (err) { console.error(err) }
    }
  }
}
</script>

<style scoped>
.reminder-list { padding: 8px; }
.add-item { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; align-items: center; }
.add-item > input { flex: 1; min-width: 100px; padding: 6px 8px; border-radius: 6px; background: var(--bg); color: var(--tc); border: 1px solid var(--border); }
.time-selects { display: flex; gap: 4px; }
.time-selects select { padding: 6px 3px; border-radius: 6px; background: var(--bg); color: var(--tc); border: 1px solid var(--border); font-size: 12px; }
.add-item .lvl-sel { padding: 6px 8px; border-radius: 6px; background: var(--bg); color: var(--tc); border: 1px solid var(--border); }
.add-item button { background: var(--p); border: none; color: #fff; border-radius: 6px; cursor: pointer; padding: 0 16px; white-space: nowrap; }
.item { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; background: var(--sb); border-radius: 6px; margin-bottom: 8px; border-left: 3px solid transparent; transition: transform .15s, background .15s, border-color .2s; }
.item:hover { background: rgba(255,255,255,.04); transform: translateX(2px); }
.item.done { opacity: 0.5; }
.item.done strong { text-decoration: line-through; }
.item[data-level="7"], .item[data-level="6"] { border-left-color: #e74c3c; }
.item[data-level="5"], .item[data-level="4"] { border-left-color: #f59e0b; }
.item[data-level="3"], .item[data-level="2"] { border-left-color: #5390d4; }
.item[data-level="1"] { border-left-color: #4caf50; }
.meta { font-size: 12px; color: var(--tc2); margin-top: 4px; }
.actions { display: flex; gap: 6px; align-items: center; }
.actions button { background: none; border: none; cursor: pointer; opacity: .4; transition: opacity .15s; color: var(--tc); }
.actions button:hover { opacity: 1; }
.btn-done { color: #4caf50 !important; font-size: 16px; font-weight: bold; opacity: 1 !important; }
.empty { text-align: center; color: var(--tc2); font-size: 13px; padding: 20px; }
</style>
