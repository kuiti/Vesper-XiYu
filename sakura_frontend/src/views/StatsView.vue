<template>
  <div class="stats-page">
    <div class="stats-header"><div class="title">数据统计</div></div>
    <div class="stats-body">
      <div class="stat-grid">
        <div class="stat-card"><div class="num">1,247</div><div class="lb">总消息</div></div>
        <div class="stat-card"><div class="num">23</div><div class="lb">聊天天数</div></div>
        <div class="stat-card"><div class="num">86%</div><div class="lb">回复率</div></div>
      </div>
      <div class="stat-grid">
        <div class="stat-card"><div class="num">65</div><div class="lb">好感度</div></div>
        <div class="stat-card"><div class="num">72</div><div class="lb">信任度</div></div>
        <div class="stat-card"><div class="num">54</div><div class="lb">今日消息</div></div>
      </div>
      <div class="chart-box"><div class="lb">消息趋势（近 14 天）</div><div class="bars"><div v-for="(h, i) in chartData" :key="i" class="bar" :class="i % 2 === 0 ? 'b1' : 'b2'" :style="{ height: h + '%' }"></div></div></div>
      <div class="chart-box"><div class="lb">情绪分布</div>
        <div class="emotion-bars"><div class="bar e1" style="width:20%"></div><div class="bar e2" style="width:65%"></div><div class="bar e3" style="width:15%"></div></div>
        <div class="emotion-legend"><span><span class="dot d1"></span> 负面 20%</span><span><span class="dot d2"></span> 中性 65%</span><span><span class="dot d3"></span> 正面 15%</span></div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
export default {
  setup() {
    const chartData = ref([30,25,45,35,20,18,60,55,80,75,50,48,70,65,40,38])
    return { chartData }
  }
}
</script>

<style scoped>
.stats-page { display: flex; flex-direction: column; height: 100%; }
.stats-header { padding: 10px 20px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.stats-header .title { font-size: 15px; font-weight: 600; }
.stats-body { flex: 1; padding: 20px; overflow-y: auto; }
.stat-grid { display: flex; gap: 8px; margin-bottom: 12px; }
.stat-card { flex: 1; background: var(--bg-card); border-radius: 10px; border: 1px solid var(--border); padding: 14px; text-align: center; }
.stat-card .num { font-size: 22px; font-weight: 700; color: var(--primary); }
.stat-card .lb { font-size: 10px; color: var(--text-muted); margin-top: 3px; }
.chart-box { background: var(--bg-card); border-radius: 10px; border: 1px solid var(--border); padding: 14px 16px; margin-bottom: 12px; }
.chart-box .lb { font-size: 11px; color: var(--text-muted); margin-bottom: 6px; }
.bars { display: flex; align-items: flex-end; gap: 3px; height: 100px; }
.bars .bar { flex: 1; border-radius: 2px 2px 0 0; min-height: 3px; }
.bar.b1 { background: linear-gradient(to top, var(--primary-dim), var(--primary)); }
.bar.b2 { background: linear-gradient(to top, hsla(160,60%,50%,.3), var(--accent)); }
.emotion-bars { display: flex; height: 24px; border-radius: 4px; overflow: hidden; gap: 2px; }
.emotion-bars .bar { border-radius: 4px; }
.bar.e1 { background: hsl(320,50%,55%); }
.bar.e2 { background: var(--primary); }
.bar.e3 { background: var(--accent); }
.emotion-legend { display: flex; gap: 12px; margin-top: 6px; font-size: 10px; color: var(--text-muted); }
.emotion-legend .dot { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 4px; }
.dot.d1 { background: hsl(320,50%,55%); } .dot.d2 { background: var(--primary); } .dot.d3 { background: var(--accent); }
</style>
