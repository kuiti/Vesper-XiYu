<template>
  <div class="nav-bar">
    <div class="nav-brand">{{ aiNameLocal }}</div>
    <div class="nav-items">
      <button v-for="item in items" :key="item.id"
        :class="['nav-btn', { active: active === item.id, 'hide-mobile': item.hideMobile }]"
        @click="$emit('nav', item.id)"
        :title="item.label"
      >
        <span class="nav-icon" v-html="item.icon"></span>
        <span class="nav-label">{{ item.label }}</span>
      </button>
      <button class="nav-btn" :class="{ active: active === 'history' }" @click="$emit('nav', 'history')" title="回顾聊天记录">
        <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></span>
        <span class="nav-label">回顾</span>
      </button>
    </div>
    <div class="nav-spacer"></div>
    <button class="nav-btn" @click="$emit('scroll-bottom')" title="回到底部 (End)">
      <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M19 12l-7 7-7-7"/></svg></span>
      <span class="nav-label">到底</span>
    </button>
    <div class="nav-status" :class="{ online: wsReady }" :title="wsReady ? '已连接' : '未连接，点击重连'" @click="!wsReady && $emit('reconnect')" :style="!wsReady ? 'cursor:pointer' : ''">
      <span class="status-dot"></span>
      <span class="status-label">{{ wsReady ? '在线' : '离线' }}</span>
    </div>
  </div>
</template>

<script>
export default {
  props: { active: String, wsReady: Boolean, totalMessages: Number, aiName: { type: String, default: '佐仓' } },
  emits: ['nav', 'scroll-bottom', 'reconnect'],
  computed: {
    aiNameLocal() { return this.aiName || '佐仓' }
  },
  data() {
    return {
      items: [
        { id: 'chat', label: '聊天', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>' },
        { id: 'diary', label: '日记', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>' },
        { id: 'tools', label: '工具', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>' },
        { id: 'stats', label: '统计', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>' },
        { id: 'memory', label: '记忆', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>' },
        { id: 'characters', label: '角色', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>' },
        { id: 'games', label: '游戏', hideMobile: true, icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M12 12h.01"/><path d="M17 10h.01"/><path d="M7 10h.01"/><path d="M12 16h.01"/><line x1="7" y1="14" x2="7" y2="14.01"/><line x1="17" y1="14" x2="17" y2="14.01"/></svg>' },
        { id: 'settings', label: '设置', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>' },
      ]
    }
  }
}
</script>

<style scoped>
/* 桌面端：左侧竖栏 */
.nav-bar { width: 60px; background: var(--sb); border-right: 1px solid var(--border); display: flex; flex-direction: column; align-items: center; padding: 12px 0; height: 100dvh; box-sizing: border-box; }
.nav-brand { font-size: 12px; font-weight: 700; color: var(--p); writing-mode: vertical-rl; letter-spacing: 4px; margin-bottom: 16px; user-select: none; }
.nav-items { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.nav-btn { display: flex; flex-direction: column; align-items: center; gap: 2px; width: 52px; padding: 8px 4px; background: none; border: none; border-radius: 8px; color: var(--tc2); cursor: pointer; transition: all .15s; min-height: 44px; justify-content: center; }
.nav-btn:hover { background: rgba(255,255,255,.04); color: var(--tc); }
.nav-btn.active { background: rgba(255,255,255,.06); color: var(--p); }
.nav-icon { width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; }
.nav-label { font-size: 10px; white-space: nowrap; }
.nav-spacer { flex: 1; }
.nav-status { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 8px 4px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: #f85149; flex-shrink: 0; }
.nav-status.online .status-dot { background: #2ea043; }
.status-label { font-size: 9px; color: var(--tc2); white-space: nowrap; }

/* 移动端：底部横栏 */
@media (max-width: 768px) {
  .nav-bar {
    width: 100%;
    height: auto;
    flex-direction: row;
    border-right: none;
    border-top: 1px solid var(--border);
    padding: 0;
    padding-bottom: env(safe-area-inset-bottom, 0);
    position: fixed;
    bottom: 0;
    left: 0;
    z-index: 1000;
  }
  .nav-brand { display: none; }
  .nav-items {
    flex-direction: row;
    flex: 1;
    gap: 0;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .nav-items::-webkit-scrollbar { display: none; }
  .nav-btn {
    width: auto;
    min-width: 48px;
    padding: 8px 6px;
    flex-shrink: 0;
  }
  .nav-label { font-size: 10px; }
  .nav-spacer { display: none; }
  .nav-status {
    flex-direction: row;
    gap: 4px;
    padding: 8px 8px;
    flex-shrink: 0;
  }
  .status-dot { width: 8px; height: 8px; }
  .status-label { font-size: 10px; }
  .hide-mobile { display: none !important; }
}
</style>
