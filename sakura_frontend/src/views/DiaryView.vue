<template>
  <div class="diary-page">
    <div class="diary-header"><div class="left"><div class="title">AI 日记</div><div class="sub">佐仓每天为你写的日记</div></div></div>
    <div class="diary-body">
      <div class="diary-bar">
        <input type="date" v-model="selectedDate" style="padding:5px 10px;background:var(--bg-card);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:12px;outline:none;color-scheme:dark;font-family:inherit">
        <button class="gen-btn" @click="generateDiary"><i class="ri-sparkling-2-line"></i> 生成今日日记</button>
        <div class="spacer"></div>
        <button class="nav-btn" @click="prevDay"><i class="ri-arrow-left-s-line"></i></button>
        <button class="nav-btn" @click="nextDay"><i class="ri-arrow-right-s-line"></i></button>
      </div>
      <div class="diary-list">
        <div v-for="entry in diaryEntries" :key="entry.date" class="diary-entry" @click="viewEntry(entry)">
          <div class="date">{{ entry.date }}</div>
          <h4>{{ entry.title }}</h4>
          <p>{{ entry.preview }}</p>
          <span class="mood-tag">{{ entry.mood }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
export default {
  setup() {
    const selectedDate = ref(new Date().toISOString().slice(0, 10))
    const diaryEntries = ref([
      { date: '2026-06-08', title: '今天聊了前端改版', preview: '用户今天在折腾前端 UI 重构，想把布局做成三栏的桌面风格……', mood: '温暖' },
      { date: '2026-06-07', title: '一起做 C 语言作业', preview: '用户今天在做 C 语言练习题，我帮他解析了几道指针和数组的题目……', mood: '充实' },
      { date: '2026-06-06', title: '晚上聊到很晚', preview: '用户加班到很晚，回来之后情绪不是很好……', mood: '心疼' },
    ])
    function generateDiary() {}
    function prevDay() { const d = new Date(selectedDate.value); d.setDate(d.getDate()-1); selectedDate.value = d.toISOString().slice(0,10) }
    function nextDay() { const d = new Date(selectedDate.value); d.setDate(d.getDate()+1); selectedDate.value = d.toISOString().slice(0,10) }
    function viewEntry(e) {}
    return { selectedDate, diaryEntries, generateDiary, prevDay, nextDay, viewEntry }
  }
}
</script>

<style scoped>
.diary-page { display: flex; flex-direction: column; height: 100%; }
.diary-header { padding: 10px 20px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.diary-header .left { display: flex; align-items: center; gap: 10px; }
.diary-header .title { font-size: 15px; font-weight: 600; }
.diary-header .sub { font-size: 12px; color: var(--text-muted); }
.diary-body { flex: 1; padding: 20px; overflow-y: auto; }
.diary-bar { display: flex; gap: 8px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
.gen-btn { padding: 5px 12px; border-radius: 6px; border: none; background: var(--primary); color: #fff; font-size: 12px; cursor: pointer; display: flex; align-items: center; gap: 6px; font-family: inherit; }
.gen-btn:hover { filter: brightness(1.1); }
.spacer { flex: 1; }
.nav-btn { width: 28px; height: 28px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg-card); color: var(--text-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; }
.nav-btn:hover { background: var(--bg-elevated); color: var(--text); }
.diary-list { display: flex; flex-direction: column; gap: 8px; }
.diary-entry { background: var(--bg-card); border-radius: 10px; border: 1px solid var(--border); padding: 14px 16px; cursor: pointer; }
.diary-entry:hover { border-color: var(--primary-dim); }
.diary-entry .date { font-size: 11px; color: var(--text-dim); }
.diary-entry h4 { font-size: 14px; font-weight: 600; margin: 2px 0 4px; }
.diary-entry p { font-size: 13px; color: var(--text-muted); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.mood-tag { display: inline-block; font-size: 10px; padding: 2px 8px; border-radius: 4px; background: var(--primary-dim); color: var(--primary); margin-top: 6px; }
</style>
