<template>
  <div class="stats-view">
    <h2>统计</h2>
    <StatsPanel />
    <div class="card" style="margin-top:14px"><h3>情感空间</h3><EmotionPanel /></div>
    <div class="card" style="margin-top:14px"><h3>洞察分析</h3><InsightPanel /></div>
    <div class="card" style="margin-top:14px"><h3>月度报告</h3><button class="btn" @click="genReport" :disabled="generating">{{ generating ? '生成中...' : '生成本月报告' }}</button><pre v-if="report" class="report">{{ report }}</pre></div>
  </div>
</template>

<script>
import StatsPanel from './StatsPanel.vue'
import EmotionPanel from './EmotionPanel.vue'
import InsightPanel from './InsightPanel.vue'
import api from '../api.js'

export default {
  components: { StatsPanel, EmotionPanel, InsightPanel },
  data() { return { generating: false, report: '' } },
  methods: {
    async genReport() { this.generating = true; try { const r = await api.get('/report/monthly'); if (r.data.ok) this.report = r.data.content } catch (e) {} this.generating = false },
  }
}
</script>

<style scoped>
.stats-view { padding: 20px; overflow-y: auto; height: 100%; }
.stats-view h2 { font-size: 18px; font-weight: 600; margin-bottom: 14px; }
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 13px; color: var(--tc2); margin-bottom: 8px; }
.btn { padding: 6px 14px; background: var(--p); color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn:disabled { opacity: .4; }
.report { margin-top: 10px; font-size: 13px; color: var(--tc); line-height: 1.8; }

/* 移动端适配 */
@media (max-width: 768px) {
  .stats-view { padding: 12px; }
  .stats-view h2 { font-size: 16px; margin-bottom: 12px; }
  .card { padding: 12px; }
  .card h3 { font-size: 14px; }
  .btn { min-height: 44px; font-size: 14px; }
  .report { font-size: 14px; }
}
</style>
