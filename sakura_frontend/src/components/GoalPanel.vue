<template>
  <div class="goal-panel">
    <div class="add-item">
      <input v-model="newGoal" placeholder="新目标，比如「学会弹吉他」" @keyup.enter="addGoal">
      <button @click="addGoal">+</button>
    </div>
    <div class="items">
      <div v-for="g in goals" :key="g.id" :class="['goal-item', { done: g.status === 'completed' }]">
        <div class="goal-main">
          <span class="goal-check" @click="toggleGoal(g)">{{ g.status === 'completed' ? '✅' : '⬜' }}</span>
          <span class="goal-text">{{ g.goal_text || g.title || g.description }}</span>
        </div>
        <button @click="deleteGoal(g.id)" class="del-btn">×</button>
      </div>
      <div v-if="!goals.length" class="empty">还没目标。设定一个试试，{{ aiName }}会帮你记住的</div>
    </div>
    <div v-if="stats" class="goal-stats">活跃 {{ stats.active || 0 }} · 完成 {{ stats.done || 0 }}</div>
  </div>
</template>

<script>
import api from '../api.js'
import { showConfirm, alert as showAlert } from '../utils/dialog.js'

export default {
  inject: { showConfirm: { default: () => async (msg) => await showConfirm({ content: msg }) } },
  props: { aiName: { type: String, default: '佐仓' } },
  data() { return { goals: [], newGoal: '', stats: null } },
  mounted() { this.load() },
  methods: {
    async load() {
      try { const [g, s] = await Promise.all([api.get('/goal/list'), api.get('/goal/stats')]); this.goals = g.data?.goals || []; this.stats = s.data || {} } catch (e) { console.error(e) }
    },
    async addGoal() {
      if (!this.newGoal.trim()) return
      try { await api.post('/goal/create', { title: this.newGoal.trim() }); this.newGoal = ''; await this.load() } catch (e) { console.error(e) }
    },
    async toggleGoal(g) {
      const ns = g.status === 'completed' ? 'active' : 'completed'
      try { await api.post(`/goal/${g.id}/status`, { status: ns }); await this.load() } catch (e) { console.error(e) }
    },
    async deleteGoal(id) {
      if (!await this.showConfirm('删除此目标？')) return
      try { await api.delete(`/goal/${id}`); await this.load() } catch (e) { console.error(e) }
    }
  }
}
</script>

<style scoped>
.goal-panel { padding: 10px; }
.add-item { display: flex; gap: 8px; margin-bottom: 12px; }
.add-item input { flex: 1; padding: 6px 8px; border-radius: 6px; background: var(--bg); color: var(--tc); border: 1px solid var(--border); }
.add-item button { background: var(--p); border: none; color: #fff; border-radius: 6px; cursor: pointer; padding: 0 14px; }
.goal-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; background: var(--sb); border-radius: 6px; margin-bottom: 6px; }
.goal-item.done .goal-text { text-decoration: line-through; opacity: .5; }
.goal-main { display: flex; align-items: center; gap: 8px; }
.goal-check { cursor: pointer; font-size: 16px; user-select: none; }
.goal-text { color: var(--tc); font-size: 14px; }
.del-btn { background: none; border: none; color: var(--tc2); cursor: pointer; opacity: .4; font-size: 16px; }
.del-btn:hover { opacity: 1; color: #e74c3c; }
.empty { text-align: center; color: var(--tc2); font-size: 13px; padding: 20px; }
.goal-stats { text-align: center; color: var(--p); font-size: 13px; margin-top: 8px; }
</style>
