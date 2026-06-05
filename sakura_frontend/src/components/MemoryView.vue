<template>
  <div class="memory-view">
    <h2>记忆</h2>
    <div class="mem-grid">
      <div class="card"><h3>记忆保险箱</h3><MemoryVault :aiName="aiName" /></div>
      <div class="card"><h3>记忆关系图</h3><MemoryGraph :aiName="aiName" /></div>
      <div class="card"><h3>AI 日记</h3><button class="btn" @click="genDiary" :disabled="diaryGenerating">{{ diaryGenerating ? '生成中...' : '生成今日日记' }}</button><div v-if="diaryContent" class="diary">{{ diaryContent }}</div></div>
    </div>
  </div>
</template>

<script>
import MemoryVault from './MemoryVault.vue'
import MemoryGraph from './MemoryGraph.vue'
import api from '../api.js'

export default {
  props: { aiName: { type: String, default: '佐仓' } },
  components: { MemoryVault, MemoryGraph },
  data() { return { diaryGenerating: false, diaryContent: '' } },
  methods: {
    async genDiary() { this.diaryGenerating = true; try { const r = await api.post('/memory/diary/generate'); if (r.data.ok) this.diaryContent = r.data.content } catch (e) {} this.diaryGenerating = false },
  }
}
</script>

<style scoped>
.memory-view { padding: 20px; overflow-y: auto; height: 100%; }
.memory-view h2 { font-size: 18px; font-weight: 600; margin-bottom: 14px; }
.mem-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 13px; color: var(--tc2); margin-bottom: 8px; }
.btn { padding: 6px 14px; background: var(--p); color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn:disabled { opacity: .4; }
.diary { margin-top: 10px; padding: 10px; background: rgba(255,255,255,.03); border-radius: 6px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; }

/* 移动端适配 */
@media (max-width: 768px) {
  .memory-view { padding: 12px; }
  .memory-view h2 { font-size: 16px; margin-bottom: 12px; }
  .mem-grid { grid-template-columns: 1fr; gap: 10px; }
  .card { padding: 12px; }
  .card h3 { font-size: 14px; }
  .btn { min-height: 44px; font-size: 14px; }
  .diary { font-size: 14px; padding: 12px; }
}
</style>
