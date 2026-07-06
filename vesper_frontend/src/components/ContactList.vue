<script setup>
import { ref } from 'vue'
import { useChat } from '../stores/chatStore.js'
import { activateCharacter, deactivateCharacter, fetchCharacters } from '../utils/api.js'

const chat = useChat()
const tab = ref('chat')

async function pick(id) {
  await activateCharacter(id)
  chat.characters = (await fetchCharacters()).characters || []
}
async function back() {
  await deactivateCharacter()
  chat.characters = (await fetchCharacters()).characters || []
}
function go(v) { if (window.__nav) window.__nav(v) }
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-dot"></span>
      <span class="brand-name">夕语</span>
    </div>

    <div class="tabs">
      <button class="tab" :class="{ active: tab === 'chat' }" @click="tab='chat'">消息</button>
      <button class="tab" @click="tab='more'; go('settings')">设置</button>
    </div>

    <div class="search">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <input class="search-inp" placeholder="搜索角色..." />
    </div>

    <div class="list">
      <div class="contact" :class="{ active: !chat.characters.some(c=>c.is_active) }" @click="back">
        <div class="av main-av">夕</div>
        <div class="info">
          <div class="name-row">
            <span class="name">默认模式</span>
            <span class="status" :class="{ on: chat.connected }">●</span>
          </div>
          <div class="preview">{{ chat.connected ? '在线' : '离线' }}</div>
        </div>
      </div>

      <div v-for="c in chat.characters" :key="c.id" class="contact" :class="{ active: c.is_active }" @click="pick(c.id)">
        <div class="av">{{ (c.name || '?')[0] }}</div>
        <div class="info">
          <div class="name-row">
            <span class="name">{{ c.name }}</span>
          </div>
          <div class="preview">{{ c.description || '暂无描述' }}</div>
        </div>
      </div>

      <div class="contact add-contact" @click="go('settings')">
        <div class="av add-av">+</div>
        <div class="info">
          <div class="name" style="color:var(--accent)">管理角色</div>
          <div class="preview">新建 / 导入 / 删除</div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  height: 100%;
  background: var(--bg-surface);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: relative;
  z-index: 2;
}

.brand {
  padding: 20px 18px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.brand-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent-start), var(--accent-end));
  box-shadow: 0 0 12px var(--accent-glow);
}
.brand-name {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, var(--accent-start), var(--accent-end));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.tabs {
  display: flex;
  padding: 0 16px 10px;
  gap: 20px;
}
.tab {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted);
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 0;
  font-family: var(--font-sans);
  position: relative;
  transition: color 0.2s;
}
.tab:hover { color: var(--text-secondary); }
.tab.active { color: var(--text); }
.tab.active::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--accent-start), var(--accent-end));
  border-radius: 1px;
}

.search {
  margin: 0 12px 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  height: 34px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-muted);
}
.search-inp {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: var(--text);
  font-family: var(--font-sans);
  font-size: 13px;
}
.search-inp::placeholder { color: var(--text-tertiary); }

.list { flex: 1; overflow-y: auto; padding: 0 8px 8px; }

.contact {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 1px;
}
.contact:hover { background: var(--bg-hover); }
.contact.active { background: var(--bg-active); }

.av {
  width: 42px;
  height: 42px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  flex-shrink: 0;
  border: 1px solid var(--border);
}
.contact.active .av { border-color: var(--accent); color: var(--accent); }
.main-av { background: linear-gradient(135deg, var(--accent-start), var(--accent-end)); color: white; border: none; }
.add-av { border: 1px dashed var(--border-light); color: var(--accent); background: transparent; }

.info { flex: 1; min-width: 0; }
.name-row { display: flex; align-items: center; gap: 6px; }
.name { font-size: 14px; font-weight: 500; }
.status { font-size: 8px; color: var(--text-tertiary); }
.status.on { color: var(--success); }
.preview { font-size: 12px; color: var(--text-muted); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
