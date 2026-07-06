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
import api from '../api'

export default {
  inject: { showConfirm: { default: () => (msg) => window.confirm(msg) } },
  data() {
    return { habits: [], newHabit: '', loading: false }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true
      try {
        const r = await api.get('/habits/')
        this.habits = (r.data || []).map(h => ({ ...h, _id: h.id }))
      } catch (e) { console.error('加载习惯失败', e) }
      this.loading = false
    },
    async addHabit() {
      if (!this.newHabit.trim()) return
      try {
        await api.post('/habits/', { name: this.newHabit.trim() })
        this.newHabit = ''
        await this.load()
      } catch (e) { console.error('添加习惯失败', e) }
    },
    async toggleDay(h) {
      const checked = !h.checked
      const streak = checked ? (h.streak || 0) + 1 : Math.max(0, (h.streak || 0) - 1)
      try {
        await api.patch('/habits/' + h.id, { checked, streak })
        h.checked = checked ? 1 : 0
        h.streak = streak
      } catch (e) { console.error('更新习惯失败', e) }
    },
    async deleteHabit(id) {
      if (!this.showConfirm) return
      try {
        await api.delete('/habits/' + id)
        await this.load()
      } catch (e) { console.error('删除习惯失败', e) }
    }
  }
}
</script>

<style scoped>
.habit-tracker { padding: 10px; }
.add-item { display: flex; gap: 8px; margin-bottom: 12px; }
.add-item input { flex: 1; padding: 6px 8px; border-radius: 6px; background: var(--surface-app); color: var(--text-primary); border: 1px solid var(--border-default); }
.add-item button { background: var(--accent-primary); border: none; color: #fff; border-radius: 6px; cursor: pointer; padding: 0 14px; }
.habit-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: var(--surface-sidebar); border-radius: 6px; margin-bottom: 6px; }
.habit-check { cursor: pointer; font-size: 16px; user-select: none; }
.habit-name { flex: 1; color: var(--text-primary); font-size: 14px; }
.habit-name.done { text-decoration: line-through; opacity: .5; }
.habit-streak { color: var(--accent-primary); font-size: 12px; font-weight: 600; }
.del-btn { background: none; border: none; color: var(--text-secondary); cursor: pointer; opacity: .4; font-size: 16px; }
.del-btn:hover { opacity: 1; color: #e74c3c; }
.empty { text-align: center; color: var(--text-secondary); font-size: 13px; padding: 20px; }
.habit-reset { text-align: center; color: var(--text-secondary); font-size: 10px; margin-top: 8px; opacity: .5; }
</style>
