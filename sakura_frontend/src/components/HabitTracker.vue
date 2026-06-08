<template>
  <div class="habit-tracker">
    <div class="add-item">
      <input v-model="newHabit" placeholder="新习惯，比如「喝水8杯」" @keyup.enter="addHabit">
      <button @click="addHabit">+</button>
    </div>
    <div class="items">
      <div v-for="h in habits" :key="h.id" class="habit-item">
        <span class="habit-check" @click="toggleDay(h)">{{ h.checked ? '✅' : '⬜' }}</span>
        <span class="habit-name" :class="{ done: h.checked }">{{ h.name }}</span>
        <span class="habit-streak" v-if="h.streak > 1">{{ h.streak }}天</span>
        <button @click="deleteHabit(h.id)" class="del-btn">×</button>
      </div>
      <div v-if="!habits.length" class="empty">还没习惯。从「喝水」或「散步」开始吧</div>
    </div>
    <div class="habit-reset">每天 0 点自动重置</div>
  </div>
</template>

<script>
const STORAGE_KEY = 'mellow_habits'

export default {
  inject: { showConfirm: { default: () => async (msg) => await showConfirm({ content: msg }) } },
  data() {
    return { habits: [], newHabit: '', _lastDate: '' }
  },
  mounted() { this.load() },
  methods: {
    load() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY)
        this.habits = raw ? JSON.parse(raw) : []
        const today = new Date().toDateString()
        const savedDate = localStorage.getItem(STORAGE_KEY + '_date') || ''
        if (savedDate && savedDate !== today) {
          this.habits.forEach(h => { if (!h.checked) h.streak = 0; h.checked = false })
          this.save()
        }
        localStorage.setItem(STORAGE_KEY + '_date', today)
      } catch (e) { this.habits = [] }
    },
    save() { localStorage.setItem(STORAGE_KEY, JSON.stringify(this.habits)) },
    addHabit() {
      if (!this.newHabit.trim()) return
      this.habits.push({ id: Date.now(), name: this.newHabit.trim(), checked: false, streak: 0 })
      this.newHabit = ''; this.save()
    },
    toggleDay(h) {
      h.checked = !h.checked
      h.streak = h.checked ? (h.streak || 0) + 1 : Math.max(0, (h.streak || 0) - 1)
      this.save()
    },
    deleteHabit(id) {
      this.habits = this.habits.filter(h => h.id !== id); this.save()
    }
  }
}
</script>

<style scoped>
.habit-tracker { padding: 10px; }
.add-item { display: flex; gap: 8px; margin-bottom: 12px; }
.add-item input { flex: 1; padding: 6px 8px; border-radius: 6px; background: var(--bg); color: var(--tc); border: 1px solid var(--border); }
.add-item button { background: var(--p); border: none; color: #fff; border-radius: 6px; cursor: pointer; padding: 0 14px; }
.habit-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: var(--sb); border-radius: 6px; margin-bottom: 6px; }
.habit-check { cursor: pointer; font-size: 16px; user-select: none; }
.habit-name { flex: 1; color: var(--tc); font-size: 14px; }
.habit-name.done { text-decoration: line-through; opacity: .5; }
.habit-streak { color: var(--p); font-size: 12px; font-weight: 600; }
.del-btn { background: none; border: none; color: var(--tc2); cursor: pointer; opacity: .4; font-size: 16px; }
.del-btn:hover { opacity: 1; color: #e74c3c; }
.empty { text-align: center; color: var(--tc2); font-size: 13px; padding: 20px; }
.habit-reset { text-align: center; color: var(--tc2); font-size: 10px; margin-top: 8px; opacity: .5; }
</style>
