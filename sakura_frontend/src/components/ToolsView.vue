<template>
  <div class="tools-view">
    <h2>工具</h2>
    <div class="tools-grid">
      <div class="tool-card"><h3>待办</h3><TodoList /></div>
      <div class="tool-card"><h3>笔记</h3><NoteList /></div>
      <div class="tool-card"><h3>倒计时</h3><CountdownList /></div>
      <div class="tool-card"><h3>提醒</h3><ReminderList /></div>
      <div class="tool-card"><h3>目标</h3><GoalPanel :aiName="aiName" /></div>
      <div class="tool-card"><h3>小习惯</h3><HabitTracker /></div>
    </div>
  </div>
</template>

<script>
import TodoList from './TodoList.vue'
import NoteList from './NoteList.vue'
import CountdownList from './CountdownList.vue'
import ReminderList from './ReminderList.vue'
import GoalPanel from './GoalPanel.vue'
import HabitTracker from './HabitTracker.vue'

export default {
  props: { aiName: { type: String, default: '佐仓' } },
  components: { TodoList, NoteList, CountdownList, ReminderList, GoalPanel, HabitTracker },
}
</script>

<style scoped>
.tools-view { padding: 20px; overflow-y: auto; height: 100%; }
.tools-view h2 { font-size: 18px; font-weight: 600; margin-bottom: 16px; color: var(--tc); }
.tools-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.tool-card { background: rgba(255,255,255,.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.tool-card h3 { font-size: 13px; color: var(--tc2); margin-bottom: 10px; }

/* 移动端适配 */
@media (max-width: 768px) {
  .tools-view { padding: 12px; }
  .tools-view h2 { font-size: 16px; margin-bottom: 12px; }
  .tools-grid { display: flex; flex-direction: column; gap: 10px; align-items: center; }
  .tool-card { padding: 10px; width: fit-content; min-width: 200px; max-width: 90%; }
  .tool-card h3 { font-size: 14px; margin-bottom: 6px; }
}
</style>
