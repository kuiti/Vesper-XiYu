<template>
  <div class="insight-panel">
    <div class="ip-tabs">
      <button :class="{ active: tab === 'goal' }" @click="tab = 'goal'">目标追踪</button>
      <button :class="{ active: tab === 'demand' }" @click="tab = 'demand'">需求模式</button>
    </div>

    <!-- 目标追踪 -->
    <div v-if="tab === 'goal'" class="ip-tab">
      <div class="ip-stats" v-if="goalStats">
        <span class="stat">活跃 {{ goalStats.active }}</span>
        <span class="stat">遗忘 {{ goalStats.stale || 0 }}</span>
        <span class="stat">完成 {{ goalStats.done }}</span>
        <span class="stat">放弃 {{ goalStats.abandoned }}</span>
      </div>
      <div class="ip-loading" v-if="loading.goal">加载中...</div>
      <div v-else-if="!goals.length" class="ip-empty">还没有追踪到目标。多聊聊你想做的事，AI 会自动识别。</div>
      <div v-else class="ip-list">
        <div v-for="g in goals" :key="g.id" :class="['ip-item', g.status]">
          <div class="ip-item-top">
            <span class="ip-cat" :class="g.category">{{ catLabel(g.category) }}</span>
            <span class="ip-status">{{ statusLabel(g.status) }}</span>
          </div>
          <div class="ip-text">{{ g.goal_text }}</div>
          <div class="ip-meta">
            <span>首次: {{ fmtDate(g.first_mentioned) }}</span>
            <span v-if="g.last_followed_up">跟进: {{ fmtDate(g.last_followed_up) }} ({{ g.follow_up_count }}次)</span>
          </div>
          <div class="ip-actions" v-if="g.status === 'active'">
            <button class="btn-s" @click="updateGoal(g.id, 'done')">已完成</button>
            <button class="btn-s btn-danger" @click="updateGoal(g.id, 'abandoned')">放弃</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 需求模式 -->
    <div v-if="tab === 'demand'" class="ip-tab">
      <div class="ip-stats" v-if="demandStats">
        <span v-for="d in demandStats" :key="d.level">{{ d.level }}: {{ d.count }}</span>
      </div>
      <div class="ip-loading" v-if="loading.demand">加载中...</div>
      <div v-else-if="!patterns.length" class="ip-empty">还没有学习到需求模式。多聊几天，AI 会逐渐了解你的习惯。</div>
      <div v-else class="ip-list">
        <div v-for="p in patterns" :key="p.trigger_context" class="ip-item">
          <div class="ip-item-top">
            <span class="ip-cat" :class="p.demand_level">{{ p.demand_level }}</span>
            <span class="ip-freq">出现 {{ p.frequency }} 次</span>
          </div>
          <div class="ip-text">触发: 「{{ p.trigger_context }}」</div>
          <div class="ip-text ip-latent" v-if="p.latent_need">深层需求: {{ p.latent_need }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api'

export default {
  name: 'InsightPanel',
  data() {
    return {
      tab: 'goal',
      loading: { goal: true, demand: true },
      error: { goal: false, demand: false },
      goals: [],
      goalStats: null,
      patterns: [],
      demandStats: []
    }
  },
  mounted() {
    this.loadGoals()
    this.loadDemand()
  },
  methods: {
    async loadGoals() {
      this.error.goal = false
      try {
        const [listRes, statsRes] = await Promise.all([
          api.get('/goal/list?status=all'),
          api.get('/goal/stats')
        ])
        this.goals = listRes.data?.goals || []
        this.goalStats = statsRes.data || {}
      } catch (e) { this.error.goal = true; console.error(e) }
      this.loading.goal = false
    },
    async loadDemand() {
      this.error.demand = false
      try {
        const [patRes, statsRes] = await Promise.all([
          api.get('/demand/patterns'),
          api.get('/demand/stats')
        ])
        this.patterns = patRes.data?.patterns || []
        this.demandStats = statsRes.data?.distribution || []
      } catch (e) { this.error.demand = true; console.error(e) }
      this.loading.demand = false
    },
    async updateGoal(id, status) {
      try {
        await api.post(`/goal/${id}/status`, { status })
        await this.loadGoals()
      } catch (e) { this.error.goal = true; console.error(e) }
    },
    catLabel(c) {
      return { learning: '学习', health: '健康', project: '项目', habit: '习惯', career: '职业' }[c] || c
    },
    statusLabel(s) {
      return { active: '追踪中', stale: '已遗忘', done: '已完成', abandoned: '已放弃' }[s] || s
    },
    fmtDate(ts) {
      if (!ts) return ''
      const d = new Date(ts)
      return `${d.getMonth()+1}/${d.getDate()}`
    }
  }
}
</script>

<style scoped>
.insight-panel { min-height: 260px; }
.ip-tabs { display: flex; gap: 4px; margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,.06); padding-bottom: 8px; }
.ip-tabs button { border: none; background: none; padding: 5px 14px; border-radius: 6px; cursor: pointer; color: #7f8c8d; font-size: 13px; }
.ip-tabs button.active { background: var(--accent-primary); color: #fff; }
.ip-tab { min-height: 180px; }
.ip-loading, .ip-empty { text-align: center; color: #7f8c8d; padding: 30px 0; font-size: 13px; }
.ip-stats { display: flex; gap: 16px; margin-bottom: 14px; font-size: 13px; }
.ip-stats .stat { color: #7f8c8d; padding: 3px 8px; border-radius: 4px; background: rgba(255,255,255,.04); }
.ip-list { max-height: 320px; overflow-y: auto; }
.ip-item { padding: 12px 14px; border-radius: 6px; background: rgba(255,255,255,.04); margin-bottom: 8px; }
.ip-item.done { opacity: 0.5; }
.ip-item.abandoned { opacity: 0.4; }
.ip-item.abandoned .ip-text { text-decoration: line-through; }
.ip-item-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.ip-cat { font-size: 12px; padding: 2px 8px; border-radius: 3px; color: #7f8c8d; border: 1px solid rgba(255,255,255,.08); }
.ip-status { font-size: 12px; color: #7f8c8d; }
.ip-text { font-size: 14px; margin-bottom: 4px; color: #ecf0f1; }
.ip-latent { color: #7f8c8d; font-size: 13px; }
.ip-meta { display: flex; gap: 12px; font-size: 12px; color: #7f8c8d; margin-bottom: 6px; }
.ip-actions { display: flex; gap: 6px; }
.ip-freq { font-size: 12px; color: #7f8c8d; }
</style>
