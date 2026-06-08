<template>
  <div class="countdown-list">
    <div class="add-item">
      <input v-model="newName" placeholder="名称" />
      <div class="date-selects">
        <select v-model.number="selYear"><option v-for="y in years" :key="y" :value="y">{{ y }}年</option></select>
        <select v-model.number="selMonth" @change="fixDay"><option v-for="m in 12" :key="m" :value="m">{{ m }}月</option></select>
        <select v-model.number="selDay"><option v-for="d in maxDay" :key="d" :value="d">{{ d }}日</option></select>
      </div>
      <button @click="addCountdown">+</button>
    </div>
    <div class="items">
      <div v-for="item in items" :key="item.id" class="item">
        <span>{{ item.name }}</span>
        <span :class="daysClass(item.target)">{{ daysRemaining(item.target) }}天</span>
        <button @click="deleteItem(item.id)" class="del-btn">删除</button>
      </div>
      <div v-if="!items.length" class="empty">还没倒计时。试试「暑假」选个日期</div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'
import { showConfirm, alert as showAlert } from '../utils/dialog.js'

export default {
  inject: { showConfirm: { default: () => async (msg) => await showConfirm({ content: msg }) } },
  data() {
    const now = new Date()
    return {
      items: [],
      newName: '',
      selYear: now.getFullYear(),
      selMonth: now.getMonth() + 1,
      selDay: now.getDate()
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
    }
  },
  mounted() {
    this.load()
    this._timer = setInterval(() => { this.$forceUpdate() }, 60000)
  },
  beforeUnmount() {
    if (this._timer) { clearInterval(this._timer); this._timer = null }
  },
  methods: {
    async load() {
      try { const res = await api.get('/countdowns/'); this.items = res.data } catch (err) { console.error(err) }
    },
    fixDay() {
      if (this.selDay > this.maxDay) this.selDay = this.maxDay
    },
    _calcDays(targetDate) {
      if (!targetDate) return NaN
      const target = new Date(targetDate + 'T23:59:59')
      const now = new Date()
      if (isNaN(target.getTime())) return NaN
      return Math.ceil((target - now) / (1000 * 60 * 60 * 24))
    },
    daysRemaining(targetDate) {
      const days = this._calcDays(targetDate)
      return days >= 0 ? days : 0
    },
    daysClass(targetDate) {
      const days = this._calcDays(targetDate)
      if (isNaN(days)) return 'days-urgent'
      if (days <= 3) return 'days-urgent'
      if (days <= 7) return 'days-soon'
      return 'days-normal'
    },
    async addCountdown() {
      if (!this.newName) return
      try {
        const mm = String(this.selMonth).padStart(2, '0')
        const dd = String(this.selDay).padStart(2, '0')
        await api.post('/countdowns/', { name: this.newName, target_date: `${this.selYear}-${mm}-${dd}` })
        this.newName = ''
        await this.load()
      } catch (err) { console.error(err) }
    },
    async deleteItem(id) {
      if (!await this.showConfirm('删除此倒计时？')) return
      try { await api.delete(`/countdowns/${id}`); await this.load() } catch (err) { console.error(err) }
    }
  }
}
</script>

<style scoped>
.countdown-list { padding: 8px; }
.add-item { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; align-items: center; }
.add-item > input { flex: 1; min-width: 100px; padding: 6px 8px; border-radius: 6px; background: var(--bg); color: var(--tc); border: 1px solid var(--border); }
.date-selects { display: flex; gap: 4px; }
.date-selects select { padding: 6px 4px; border-radius: 6px; background: var(--bg); color: var(--tc); border: 1px solid var(--border); font-size: 13px; }
.add-item button { background: var(--p); border: none; color: #fff; border-radius: 6px; cursor: pointer; padding: 0 12px; white-space: nowrap; }
.item { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; background: var(--sb); border-radius: 6px; margin-bottom: 6px; transition: transform .15s, background .15s; }
.item:hover { background: rgba(255,255,255,.04); transform: translateX(2px); }
.item span { color: var(--tc); }
.item button { background: none; border: none; color: #e74c3c; cursor: pointer; opacity: .4; transition: opacity .15s; }
.item button:hover { opacity: 1; }
.empty { text-align: center; color: var(--tc2); font-size: 13px; padding: 20px; }
.days-urgent { color: #e74c3c !important; font-weight: 600; }
.days-soon { color: #f59e0b !important; }
.days-normal { color: #4caf50 !important; }
</style>
