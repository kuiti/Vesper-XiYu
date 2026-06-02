<template>
  <div class="stats-panel">
    <div class="stats-grid">
      <div class="stat-card"><div class="stat-num">{{ data.total_messages || 0 }}</div><div class="stat-label">总消息数</div></div>
      <div class="stat-card"><div class="stat-num">{{ data.total_days || 0 }}</div><div class="stat-label">互动天数</div></div>
      <div class="stat-card"><div class="stat-num">{{ data.avg_daily || 0 }}</div><div class="stat-label">日均消息</div></div>
      <div class="stat-card"><div class="stat-num">{{ data.user_messages || 0 }}/{{ data.ai_messages || 0 }}</div><div class="stat-label">用户/AI 消息</div></div>
    </div>
    <div class="stat-section">
      <h4>活跃时段分布</h4>
      <div class="hour-bars">
        <div v-for="(cnt, h) in data.hourly_dist || {}" :key="h" class="hour-bar-wrap">
          <div class="hour-bar" :style="{ height: barHeight(cnt) + '%' }" :title="h+'点: '+cnt+'条'"></div>
          <span class="hour-label">{{ h }}</span>
        </div>
      </div>
    </div>
    <div class="stat-section">
      <h4>情绪分布</h4>
      <div class="emotion-pie">
        <div class="pie-slice pos" :style="{ flex: (data.emotion_dist||{}).positive || 0 }">正面 {{ (data.emotion_dist||{}).positive || 0 }}</div>
        <div class="pie-slice neu" :style="{ flex: (data.emotion_dist||{}).neutral || 0 }">中性 {{ (data.emotion_dist||{}).neutral || 0 }}</div>
        <div class="pie-slice neg" :style="{ flex: (data.emotion_dist||{}).negative || 0 }">负面 {{ (data.emotion_dist||{}).negative || 0 }}</div>
      </div>
    </div>
    <div class="stat-section" v-if="data.top_words && data.top_words.length">
      <h4>关键词云</h4>
      <div class="word-cloud">
        <span v-for="w in data.top_words" :key="w.word" class="word-tag" :style="{ fontSize: (12 + Math.log(Math.max(w.count, 1))*3) + 'px' }">{{ w.word }}</span>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  data() { return { data: {} } },
  async mounted() {
    try { const res = await api.get('/stats/overview'); this.data = res.data || {} } catch (e) { this.data = {}; console.error(e) }
  },
  methods: {
    barHeight(cnt) { const max = Math.max(...Object.values(this.data.hourly_dist || {0:1})); return max > 0 ? (cnt/max*100) : 0 }
  }
}
</script>

<style scoped>
.stats-panel { padding: 8px; }
.stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 16px; }
.stat-card { background: rgba(255,255,255,.04); border-radius: 8px; padding: 14px; text-align: center; }
.stat-num { font-size: 24px; font-weight: 700; color: var(--p); }
.stat-label { font-size: 11px; color: var(--tc2); margin-top: 2px; }
.stat-section { margin-bottom: 14px; }
.stat-section h4 { font-size: 13px; color: var(--tc2); margin: 0 0 8px; }
.hour-bars { display: flex; gap: 2px; align-items: flex-end; height: 80px; }
.hour-bar-wrap { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
.hour-bar { width: 100%; max-width: 20px; background: var(--p); border-radius: 2px 2px 0 0; min-height: 2px; transition: height .3s; }
.hour-label { font-size: 9px; color: var(--tc2); margin-top: 2px; }
.emotion-pie { display: flex; height: 24px; border-radius: 12px; overflow: hidden; }
.pie-slice { display: flex; align-items: center; justify-content: center; font-size: 11px; color: #fff; min-width: 0; }
.pie-slice.pos { background: #2ea043; }
.pie-slice.neu { background: #6e7681; }
.pie-slice.neg { background: #da3633; }
.word-cloud { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.word-tag { color: var(--tc); opacity: .8; cursor: default; }
</style>
