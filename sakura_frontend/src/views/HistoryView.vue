<template>
  <div class="history-page">
    <div class="history-header"><div class="left"><div class="title">回顾</div></div><div class="actions"><i class="ri-search-line"></i></div></div>
    <div class="history-body">
      <div class="filter-bar">
        <span style="font-size:11px;color:var(--text-muted)">从</span>
        <input type="date" v-model="dateFrom" style="padding:5px 10px;background:var(--bg-card);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:12px;outline:none;color-scheme:dark;font-family:inherit">
        <span style="font-size:11px;color:var(--text-muted)">至</span>
        <input type="date" v-model="dateTo" style="padding:5px 10px;background:var(--bg-card);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:12px;outline:none;color-scheme:dark;font-family:inherit">
        <div class="spacer"></div>
        <span style="font-size:11px;color:var(--text-muted)">{{ filteredHistory.length }} 条记录</span>
      </div>
      <div class="history-list">
        <div v-for="(item, i) in filteredHistory" :key="i" class="history-item">
          <span class="day">{{ item.day }}</span>
          <span class="preview">{{ item.text }}</span>
          <button :class="['fav-btn', { on: item.fav }]" @click="item.fav = !item.fav">
            <i :class="item.fav ? 'ri-star-fill' : 'ri-star-line'"></i>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'
export default {
  setup() {
    const dateFrom = ref('2026-06-01')
    const dateTo = ref('2026-06-08')
    const allHistory = ref([
      { day: '今天', text: '在改前端 UI，想把排版做好看点', fav: false },
      { day: '昨天', text: 'C 语言那个指针的题我还是不太懂', fav: true },
      { day: '06/06', text: '今天加班好累，感觉项目 deadline 要赶不上了', fav: false },
      { day: '06/05', text: '今天试了一下新模型，感觉比之前的好', fav: false },
      { day: '06/04', text: '你觉得我应该学 Rust 还是继续深耕前端？', fav: true },
    ])
    const filteredHistory = computed(() => allHistory.value)
    return { dateFrom, dateTo, filteredHistory }
  }
}
</script>

<style scoped>
.history-page { display: flex; flex-direction: column; height: 100%; }
.history-header { padding: 10px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.history-header .left { display: flex; align-items: center; }
.history-header .title { font-size: 15px; font-weight: 600; }
.history-header .actions { display: flex; gap: 6px; color: var(--text-muted); font-size: 18px; cursor: pointer; }
.history-body { flex: 1; padding: 20px; overflow-y: auto; }
.filter-bar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; flex-wrap: wrap; }
.filter-bar input:focus { border-color: var(--primary); }
.spacer { flex: 1; }
.history-list { display: flex; flex-direction: column; gap: 1px; }
.history-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 6px; cursor: pointer; }
.history-item:hover { background: var(--bg-card); }
.history-item .day { font-size: 11px; color: var(--text-dim); width: 50px; flex-shrink: 0; }
.history-item .preview { font-size: 13px; color: var(--text-muted); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fav-btn { color: var(--text-dim); cursor: pointer; font-size: 13px; border: none; background: none; }
.fav-btn.on { color: hsl(38,100%,60%); }
</style>
