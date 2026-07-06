<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const props = defineProps({ msg: Object, index: Number })
const emit = defineEmits(['feedback', 'tts', 'ctxmenu'])
import { useChat } from '../stores/chatStore.js'
const chat = useChat()

function fmtTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ''
  const now = new Date(), diff = now - d, min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return min + '分钟前'
  if (d.toDateString() === now.toDateString()) return String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0')
  const yd = new Date(now); yd.setDate(now.getDate() - 1)
  if (d.toDateString() === yd.toDateString()) return '昨天 ' + String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0')
  return (d.getMonth()+1) + '/' + d.getDate() + ' ' + String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0')
}

function renderMd(t) {
  if (!t) return ''
  const html = md.render(t)
  // Strip outer <p> wrapper if it wraps the entire content
  return html.replace(/^<p>([\s\S]*)<\/p>\n?$/, '$1')
}

function onCtx(e) { emit('ctxmenu', e, props.msg) }
function copyText(t) { navigator.clipboard.writeText(t).catch(() => {}) }

const bubbleContent = computed(() => renderMd(props.msg.content))
</script>

<template>
  <div class="row" :class="[msg.role, { proactive: msg.isProactive }]" :style="{ animationDelay: (index || 0) * 25 + 'ms' }">
    <template v-if="msg.role === 'assistant'">
      <div class="av" @contextmenu.prevent="onCtx">
        <img v-if="chat.aiAvatarUrl" :src="chat.aiAvatarUrl" class="av-img" />
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2a4 4 0 0 1 4 4c0 2-2 4-4 4s-4-2-4-4a4 4 0 0 1 4-4z"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/></svg>
      </div>
      <div class="content">
        <div class="name">
          <span>夕语</span>
          <span v-if="msg._emotion" class="emo">{{ msg._emotion === 'happy' ? '😊' : msg._emotion === 'sad' ? '😢' : msg._emotion === 'angry' ? '😠' : msg._emotion === 'surprise' ? '😲' : msg._emotion === 'love' ? '🥰' : '😌' }}</span>
        </div>
        <div class="bubble" v-html="bubbleContent" @contextmenu.prevent="onCtx" @dblclick="copyText(msg.content)"></div>
        <div class="footer">
          <span class="time">{{ fmtTime(msg.timestamp) }}</span>
          <button v-if="msg.role === 'assistant' && msg.content" class="fbtn" @click="emit('tts', msg)" title="朗读">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="11,5 6,9 2,9 2,15 6,15 11,19"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
          </button>
          <div v-if="msg.role === 'assistant' && msg.id && !msg._feedback" class="fb">
            <button class="fbtn" @click="emit('feedback', msg, 1)" title="赞"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg></button>
            <button class="fbtn" @click="emit('feedback', msg, -1)" title="踩"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10zM17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg></button>
          </div>
          <span v-if="msg._feedback === 1" class="fb-done liked">+1</span>
          <span v-else-if="msg._feedback === -1" class="fb-done disliked">-1</span>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="content user-content">
        <div class="bubble user-bubble" v-html="bubbleContent" @dblclick="copyText(msg.content)"></div>
        <div class="footer user-footer"><span class="time">{{ fmtTime(msg.timestamp) }}</span></div>
      </div>
      <div class="av user-av">
        <img v-if="chat.userAvatarUrl" :src="chat.userAvatarUrl" class="av-img" />
        <span v-else>我</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.av-img { width:100%; height:100%; object-fit:cover; border-radius:var(--r-md); }
.row { display:flex; gap:8px; max-width:85%; animation:pop 0.2s cubic-bezier(0.16,1,0.3,1) both; }
@keyframes pop { from { opacity:0; transform:translateY(6px) scale(.98); } to { opacity:1; transform:translateY(0) scale(1); } }
.row.user { margin-left:auto; flex-direction:row-reverse; }
.row.proactive { opacity:.85; }
.row.proactive .bubble { border-left:2px solid var(--accent); }

.av { width:32px; height:32px; border-radius:var(--r-md); display:flex; align-items:center; justify-content:center; flex-shrink:0; margin-top:4px; background:rgba(255,255,255,.04); color:var(--text-muted); border:1px solid var(--border); cursor:context-menu; overflow:hidden; }
.user-av { background:var(--accent-soft); color:var(--accent); border:none; font-size:11px; font-weight:600; }

.content { display:flex; flex-direction:column; gap:2px; min-width:0; }
.user-content { align-items:flex-end; }
.name { font-size:11px; color:var(--text-muted); padding-left:4px; font-weight:500; margin-bottom:1px; display:flex; align-items:center; gap:4px; }
.emo { font-size:13px; cursor:help; }

.bubble { padding:9px 14px; font-size:14px; line-height:1.55; word-break:break-word; white-space:pre-wrap; }
.assistant .bubble { background:var(--msg-other); border:1px solid var(--msg-other-border); border-radius:4px var(--r-lg) var(--r-lg) var(--r-lg); cursor:context-menu; }
.user .bubble { background:var(--msg-self); color:white; border-radius:var(--r-lg) 4px var(--r-lg) var(--r-lg); }
.bubble :deep(a) { color:var(--accent); }
.bubble :deep(code) { background:rgba(255,255,255,.06); padding:1px 4px; border-radius:3px; font-size:13px; font-family:var(--font-mono); }
.bubble :deep(pre) { background:rgba(0,0,0,.3); padding:10px; border-radius:var(--r-md); overflow-x:auto; margin:6px 0; }
.bubble :deep(pre code) { background:none; padding:0; }
.bubble :deep(table) { border-collapse:collapse; margin:6px 0; width:100%; }
.bubble :deep(th), .bubble :deep(td) { border:1px solid var(--border); padding:4px 8px; text-align:left; font-size:13px; }
.bubble :deep(th) { background:var(--bg-hover); }
.bubble :deep(blockquote) { border-left:3px solid var(--accent); margin:6px 0; padding:4px 10px; color:var(--text-muted); }
.bubble :deep(ul), .bubble :deep(ol) { padding-left:18px; margin:4px 0; }
.bubble :deep(hr) { border:none; border-top:1px solid var(--border); margin:8px 0; }
.bubble::selection { background:var(--accent-soft); }

.footer { display:flex; align-items:center; gap:6px; margin-top:2px; padding-left:4px; height:18px; }
.user-footer { justify-content:flex-end; padding-right:4px; }
.time { font-size:10px; color:var(--text-tertiary); }
.fbtn { background:none; border:none; cursor:pointer; color:var(--text-tertiary); opacity:0; transition:all .15s; padding:2px; display:flex; align-items:center; border-radius:2px; }
.row:hover .fbtn { opacity:.5; }
.fbtn:hover { opacity:1 !important; color:var(--accent); }
.fb { display:flex; gap:2px; }
.fb-done { font-size:10px; opacity:.6; }
.liked { color:var(--accent); }
.disliked { color:#e74c3c; }
</style>
