<script setup>
import { useRouter, useRoute } from 'vue-router'
import { useChat } from '../stores/chatStore.js'
import { activateCharacter, deactivateCharacter, fetchCharacters } from '../utils/api.js'

const router = useRouter()
const route = useRoute()
const chat = useChat()

async function switchChar(id) {
  await activateCharacter(id)
  chat.characters = (await fetchCharacters()).characters || []
  router.push('/chat')
}
async function resetDefault() {
  await deactivateCharacter()
  chat.characters = (await fetchCharacters()).characters || []
  router.push('/chat')
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand" @click="router.push('/chat')">
      <div class="bi"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg></div>
      <span class="bt">夕语</span>
    </div>

    <div class="contacts">
      <div class="c" :class="{ active: route.path === '/chat' && !chat.characters.some(x => x.is_active) }" @click="resetDefault">
        <div class="av ma">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/></svg>
        </div>
        <div class="cb"><div class="cn">夕语 AI</div><div class="cp">{{ chat.connected ? '在线' : '离线' }}</div></div>
      </div>
      <div v-for="c in chat.characters" :key="c.id" class="c" :class="{ active: c.is_active }">
        <div class="av" @click="switchChar(c.id)">{{ (c.name || '?')[0] }}</div>
        <div class="cb" @click="switchChar(c.id)"><div class="cn">{{ c.name }}</div><div class="cp">{{ c.description || ' ' }}</div></div>
        <button class="cset" @click.stop="router.push('/char/' + c.id)" title="角色设置">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
        </button>
      </div>
    </div>

    <div class="sp"></div>

    <div class="nav">
      <div class="ni" :class="{ active: route.path === '/chat' }" @click="router.push('/chat')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span>对话</span>
      </div>
      <div class="ni" :class="{ active: route.path.startsWith('/settings') }" @click="router.push('/settings')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
        <span>设置</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar { width:var(--sidebar-w); height:100%; background:var(--bg-sidebar); border-right:1px solid var(--border); display:flex; flex-direction:column; flex-shrink:0; }
.brand { display:flex; align-items:center; gap:10px; padding:0 18px; height:var(--topbar-h); border-bottom:1px solid var(--border); cursor:pointer; flex-shrink:0; }
.bi { width:32px; height:32px; border-radius:var(--r-md); background:var(--accent-gradient); display:flex; align-items:center; justify-content:center; color:white; }
.bt { font-size:17px; font-weight:700; letter-spacing:0.5px; }

.contacts { padding:6px 8px; max-height:45%; overflow-y:auto; border-bottom:1px solid var(--border); }
.c { display:flex; align-items:center; gap:10px; padding:8px 10px; border-radius:var(--r-md); cursor:pointer; transition:background 0.1s; margin-bottom:1px; }
.c:hover { background:var(--bg-hover); }
.c.active { background:var(--accent-soft); }
.av { width:38px; height:38px; border-radius:var(--r-lg); display:flex; align-items:center; justify-content:center; flex-shrink:0; background:rgba(255,255,255,0.04); border:1px solid var(--border); font-size:15px; font-weight:600; color:var(--text-secondary); }
.c.active .av { border-color:var(--accent); color:var(--accent); }
.ma { background:var(--accent-gradient); color:white; border:none; }
.cb { flex:1; min-width:0; }
.cn { font-size:13px; font-weight:500; }
.cp { font-size:11px; color:var(--text-muted); margin-top:1px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.cset { width:24px; height:24px; border-radius:var(--r-sm); border:none; background:transparent; color:var(--text-muted); cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; transition:all 0.1s; }
.cset:hover { background:var(--bg-hover); color:var(--text); }
.cset:hover { background:var(--bg-hover); color:var(--text-secondary); }

.sp { flex:1; }

.nav { padding:8px; display:flex; flex-direction:column; gap:1px; }
.ni { display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:var(--r-md); cursor:pointer; transition:all 0.1s; color:var(--text-muted); font-size:13px; font-weight:500; }
.ni:hover { background:var(--bg-hover); color:var(--text-secondary); }
.ni.active { background:var(--accent-soft); color:var(--accent); }
.ni :deep(svg) { width:18px; height:18px; }
</style>
