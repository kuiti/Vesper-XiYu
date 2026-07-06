<template>
  <div class="page-view">
    <PageHeader title="工具" desc="倒计时、纪念日、目标、习惯、知识库" />
    <div class="page-body">
      <CollapsibleSection v-for="tool in tools" :key="tool.title" :title="tool.title" :defaultOpen="false">
        <component :is="tool.comp" :aiName="aiName" />
      </CollapsibleSection>
    </div>
  </div>
</template>

<script>
import PageHeader from './common/PageHeader.vue'
import CollapsibleSection from './common/CollapsibleSection.vue'
import CountdownList from './CountdownList.vue'
import GoalPanel from './GoalPanel.vue'
import HabitTracker from './HabitTracker.vue'
import RAGPanel from './RAGPanel.vue'

export default {
  props: { aiName: { type: String, default: '佐仓' } },
  components: { PageHeader, CollapsibleSection, CountdownList, GoalPanel, HabitTracker, RAGPanel },
  computed: {
    tools() {
      return [
        { title: '倒计时', comp: CountdownList },
        { title: '目标', comp: GoalPanel },
        { title: '习惯', comp: HabitTracker },
        { title: '知识库', comp: RAGPanel },
      ]
    },
  },
}
</script>
