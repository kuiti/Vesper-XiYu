<template>
  <div class="tools-page">
    <div class="tools-header"><div class="title">实用工具</div></div>
    <div class="tools-body">
      <div v-for="group in toolGroups" :key="group.label" class="tool-group">
        <div class="group-header" @click="group.open = !group.open">
          <i :class="group.open ? 'ri-arrow-down-s-line' : 'ri-arrow-right-s-line'"></i> {{ group.label }}
        </div>
        <div v-show="group.open" class="group-body">
          <div v-for="item in group.items" :key="item.name" class="tool-row" @click="item.action">
            <div class="tool-icon"><i :class="item.icon"></i></div>
            <div class="tool-info"><div class="name">{{ item.name }}</div><div class="desc">{{ item.desc }}</div></div>
            <i class="ri-arrow-right-s-line arrow"></i>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'

export default {
  setup() {
    const router = useRouter()
    const toolGroups = reactive([
      { label: '知识管理', open: true, items: [
        { name: '知识库', desc: '上传文档，AI 自动学习内容', icon: 'ri-ai-generate', action: () => {} },
        { name: 'RAG 索引', desc: '向量检索增强，记忆更精准', icon: 'ri-database-2-line', action: () => {} },
      ]},
      { label: '效率工具', open: true, items: [
        { name: '目标追踪', desc: '记录和管理你的各项目标', icon: 'ri-flag-2-line', action: () => {} },
        { name: '习惯打卡', desc: '每日习惯养成记录', icon: 'ri-checkbox-line', action: () => {} },
        { name: '笔记', desc: '随时记录灵感和想法', icon: 'ri-sticky-note-line', action: () => {} },
        { name: '倒计时', desc: '重要日期的倒计时提醒', icon: 'ri-timer-2-line', action: () => {} },
        { name: '提醒', desc: '定时提醒事项', icon: 'ri-notification-3-line', action: () => {} },
      ]},
      { label: '数据管理', open: true, items: [
        { name: '聊天管理', desc: '清理和导出聊天记录', icon: 'ri-delete-bin-line', action: () => {} },
      ]},
    ])
    return { toolGroups }
  }
}
</script>

<style scoped>
.tools-page { display: flex; flex-direction: column; height: 100%; }
.tools-header { padding: 10px 20px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.tools-header .title { font-size: 15px; font-weight: 600; }
.tools-body { flex: 1; overflow-y: auto; padding: 16px; }
.tool-group { margin-bottom: 8px; }
.group-header { display: flex; align-items: center; gap: 8px; padding: 6px 4px; cursor: pointer; font-size: 11px; color: var(--text-dim); font-weight: 600; letter-spacing: .5px; user-select: none; border-radius: 4px; }
.group-header:hover { color: var(--text-muted); }
.group-header i { font-size: 12px; }
.group-body { display: flex; flex-direction: column; gap: 1px; }
.tool-row { display: flex; align-items: center; gap: 12px; padding: 9px 14px; border-radius: 8px; color: var(--text); cursor: pointer; }
.tool-row:hover { background: var(--bg-card); }
.tool-icon { width: 34px; height: 34px; border-radius: 8px; background: var(--primary-dim); display: flex; align-items: center; justify-content: center; font-size: 17px; color: var(--primary); flex-shrink: 0; }
.tool-info { flex: 1; }
.tool-info .name { font-size: 13px; font-weight: 500; }
.tool-info .desc { font-size: 11px; color: var(--text-muted); margin-top: 1px; }
.arrow { color: var(--text-dim); font-size: 14px; }
</style>
