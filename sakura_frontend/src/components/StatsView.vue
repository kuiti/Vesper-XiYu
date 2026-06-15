<template>
  <div class="page-view">
    <PageHeader title="统计" desc="聊天数据、关系趋势、情绪变化" />
    <div class="page-body">
      <CollapsibleSection title="总览" :defaultOpen="true">
        <StatsPanel />
      </CollapsibleSection>
      <CollapsibleSection title="情感空间" :defaultOpen="true">
        <EmotionPanel />
      </CollapsibleSection>
      <CollapsibleSection title="洞察分析" :defaultOpen="true">
        <InsightPanel />
      </CollapsibleSection>
      <CollapsibleSection title="月度报告" :defaultOpen="false">
        <button class="btn" @click="genReport" :disabled="generating">{{ generating ? '生成中...' : '生成本月报告' }}</button>
        <pre v-if="report" class="report">{{ report }}</pre>
      </CollapsibleSection>
    </div>
  </div>
</template>

<script>
import PageHeader from './common/PageHeader.vue'
import CollapsibleSection from './common/CollapsibleSection.vue'
import StatsPanel from './StatsPanel.vue'
import EmotionPanel from './EmotionPanel.vue'
import InsightPanel from './InsightPanel.vue'
import api from '../api'

export default {
  components: { PageHeader, CollapsibleSection, StatsPanel, EmotionPanel, InsightPanel },
  data() { return { generating: false, report: '' } },
  methods: {
    async genReport() { this.generating = true; try { const r = await api.get('/report/monthly'); if (r.data.ok) this.report = r.data.content } catch (e) {} this.generating = false },
  }
}
</script>

<style scoped>
.report { margin-top: 8px; font-size: 13px; color: var(--text-primary); line-height: 1.8; white-space: pre-wrap; }
</style>
