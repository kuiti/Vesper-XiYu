<template>
  <div class="chat-layout">
    <!-- 侧栏 -->
    <div class="chat-panel" :class="{ collapsed: !panelOpen }">
      <div class="panel-header">
        <span>佐仓 <span class="ver">v5.0</span></span>
        <span class="collapse-btn" @click="panelOpen = !panelOpen"><i class="ri-layout-left-2-line"></i></span>
      </div>
      <div class="panel-list">
        <div class="p-section">当前</div>
        <div class="p-item active"><span class="dot on"></span> 日常闲聊</div>
        <div class="p-item"><span class="dot"></span> 记忆快照</div>
        <div class="p-item"><span class="dot y"></span> 待办 · 3</div>
        <div class="p-item"><span class="dot"></span> 近期日程</div>
        <div class="p-section">关系</div>
        <div class="aff-bar">
          <div class="aff-row"><span>好感</span><span>65</span></div>
          <div class="aff-track"><div class="fill" style="width:65%"></div></div>
          <div class="aff-row"><span>信任</span><span>72</span></div>
          <div class="aff-track"><div class="fill" style="width:72%"></div></div>
          <div class="aff-row" style="margin-top:8px"><span>连续</span><span>5 天</span></div>
        </div>
      </div>
      <button class="sb-btn" @click="scrollBottom"><i class="ri-arrow-down-s-line"></i> 一键到底</button>
    </div>

    <!-- 主区 -->
    <div class="chat-main">
      <div class="chat-header">
        <div class="left">
          <i class="ri-menu-fold-line toggle-btn" @click="panelOpen = !panelOpen"></i>
          <div><div class="title">日常闲聊</div><div class="sub">今天 · {{ messages.length }} 条消息</div></div>
        </div>
        <div class="actions"><i class="ri-search-line"></i><i class="ri-more-2-fill"></i></div>
      </div>

      <!-- 消息 -->
      <div class="messages" ref="msgListRef">
        <div class="date-sep">今天</div>
        <div v-for="(msg, i) in messages" :key="msg.id || i"
          :class="['msg', msg.role === 'user' ? 'right' : 'left',
            i > 0 && messages[i-1].role === msg.role ? 'cont' : '']"
        >
          <div v-if="msg.role === 'assistant'" class="msg-av">{{ aiInitial }}</div>
          <div class="msg-body">
            <div class="msg-bub">{{ msg.content }}</div>
            <div v-if="msg.time" class="msg-time">{{ msg.time }}</div>
          </div>
          <div v-if="msg.role === 'user'" class="msg-av user">U</div>
        </div>
        <div v-if="isStreaming" class="typing"><div class="msg-av">{{ aiInitial }}</div><div class="typing-dots"><span></span><span></span><span></span></div></div>
      </div>

      <!-- 输入 -->
      <div class="input-area"><div class="input-wrap">
        <input v-model="inputText" placeholder="说点什么 ..." @keydown.enter.exact="send">
        <div class="input-acts"><i class="ri-emotion-line"></i><i class="ri-attachment-2"></i><i class="ri-send-plane-fill send" @click="send"></i></div>
      </div></div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useChatStore } from '../stores/chat.js'

export default {
  setup() {
    const chatStore = useChatStore()
    const msgListRef = ref(null)
    const inputText = ref('')
    const panelOpen = ref(true)
    const isStreaming = ref(false)
    const aiInitial = ref('佐')
    const messages = ref([])

    function send() {
      const text = inputText.value.trim()
      if (!text || isStreaming.value) return
      inputText.value = ''
      const now = new Date()
      messages.value.push({
        role: 'user', content: text,
        time: String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0')
      })
      isStreaming.value = true
      // In real impl, send via WebSocket
    }

    function scrollBottom() {
      const el = msgListRef.value
      if (el) el.scrollTop = el.scrollHeight
    }

    onMounted(() => {
      const onScroll = () => scrollBottom()
      window.addEventListener('scroll-chat', onScroll)
      return () => window.removeEventListener('scroll-chat', onScroll)
    })

    return {
      msgListRef, inputText, panelOpen, isStreaming,
      messages, aiInitial, send, scrollBottom,
    }
  }
}
</script>

<style scoped>
.chat-layout { display: flex; flex: 1; min-height: 0; }
.chat-panel {
  width: 200px; background: var(--bg-base); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; transition: width .2s; overflow: hidden; flex-shrink: 0;
}
.chat-panel.collapsed { width: 0; border: none; }
.panel-header { padding: 14px; font-size: 13px; font-weight: 600; display: flex; align-items: center; justify-content: space-between; white-space: nowrap; flex-shrink: 0; }
.panel-header .ver { font-size: 10px; color: var(--text-dim); font-weight: 400; }
.panel-header .collapse-btn { font-size: 14px; color: var(--text-muted); cursor: pointer; }
.panel-list { flex: 1; overflow-y: auto; padding: 4px 8px; }
.p-section { font-size: 10px; color: var(--text-dim); letter-spacing: .5px; padding: 10px 10px 4px; font-weight: 500; }
.p-item { padding: 7px 10px; border-radius: 6px; cursor: pointer; font-size: 13px; color: var(--text-muted); margin-bottom: 1px; display: flex; align-items: center; gap: 10px; white-space: nowrap; }
.p-item:hover { background: var(--bg-elevated); color: var(--text); }
.p-item.active { background: var(--bg-elevated); color: var(--text); }
.p-item .dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.p-item .dot.on { background: var(--accent); }
.p-item .dot.y { background: hsl(38,80%,55%); }
.aff-bar { padding: 0 10px 12px; }
.aff-row { display: flex; justify-content: space-between; font-size: 10px; color: var(--text-muted); margin-bottom: 2px; }
.aff-track { height: 3px; background: var(--bg-card); border-radius: 2px; overflow: hidden; margin-bottom: 6px; }
.aff-track .fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, var(--primary), var(--accent)); }
.sb-btn {
  width: 100%; padding: 7px 14px; display: flex; align-items: center; gap: 8px;
  border-top: 1px solid var(--border); cursor: pointer;
  color: var(--text-dim); font-size: 11px; background: none; font-family: inherit; flex-shrink: 0;
}
.sb-btn:hover { color: var(--text-muted); background: var(--bg-elevated); }
.sb-btn i { font-size: 14px; }

.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.chat-header {
  padding: 10px 20px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; min-height: 49px;
}
.chat-header .left { display: flex; align-items: center; gap: 10px; }
.chat-header .toggle-btn { font-size: 18px; color: var(--text-muted); cursor: pointer; }
.chat-header .title { font-size: 15px; font-weight: 600; }
.chat-header .sub { font-size: 12px; color: var(--text-muted); margin-top: 1px; }
.chat-header .actions { display: flex; gap: 6px; color: var(--text-muted); font-size: 18px; }
.chat-header .actions i { padding: 4px; border-radius: 6px; cursor: pointer; }
.chat-header .actions i:hover { background: var(--bg-card); color: var(--text); }

.messages { flex: 1; overflow-y: auto; padding: 12px 20px; display: flex; flex-direction: column; }
.date-sep { text-align: center; font-size: 11px; color: var(--text-dim); padding: 12px 0 10px; position: relative; }
.date-sep::before, .date-sep::after { content: ''; position: absolute; top: 50%; width: calc(50% - 70px); height: 1px; background: var(--border); }
.date-sep::before { left: 0; } .date-sep::after { right: 0; }

.msg { display: flex; gap: 8px; max-width: 75%; }
.msg.right { align-self: flex-end; flex-direction: row-reverse; }
.msg.left { align-self: flex-start; }
.msg + .msg { margin-top: 2px; }
.msg-av {
  width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; color: #fff; margin-top: 4px; opacity: 0;
}
.msg.left .msg-av { background: hsl(260,30%,45%); }
.msg.right .msg-av { background: hsl(160,30%,45%); }
.msg:not(.cont) .msg-av { opacity: 1; }
.msg-body { display: flex; flex-direction: column; }
.msg.right .msg-body { align-items: flex-end; }
.msg-bub { padding: 7px 13px; font-size: 14px; line-height: 1.55; word-break: break-word; }
.msg.right .msg-bub { background: var(--bubble-user); color: #fff; border-radius: 16px 4px 16px 16px; }
.msg.right:not(.cont) .msg-bub { border-top-right-radius: 16px; }
.msg.right.cont .msg-bub { border-top-right-radius: 4px; }
.msg.left .msg-bub { background: var(--bubble-ai); color: var(--text); border-radius: 4px 16px 16px 16px; }
.msg.left:not(.cont) .msg-bub { border-top-left-radius: 16px; }
.msg.left.cont .msg-bub { border-top-left-radius: 4px; }
.msg-time { font-size: 10px; color: var(--text-dim); margin-top: 3px; padding: 0 4px; }
.msg.right .msg-time { text-align: right; }

.typing { display: flex; gap: 8px; align-items: center; padding: 8px 0; }
.typing .msg-av { opacity: 1; }
.typing-dots { display: flex; gap: 3px; padding: 10px 14px; background: var(--bubble-ai); border-radius: 16px; }
.typing-dots span { width: 7px; height: 7px; border-radius: 50%; background: var(--text-muted); animation: p 1.4s infinite; }
.typing-dots span:nth-child(2) { animation-delay: .2s; }
.typing-dots span:nth-child(3) { animation-delay: .4s; }
@keyframes p { 0%,60%,100%{opacity:.3}30%{opacity:1} }

.input-area { padding: 12px 20px 16px; border-top: 1px solid var(--border); flex-shrink: 0; }
.input-wrap {
  display: flex; align-items: center; gap: 8px;
  background: var(--bg-base); border: 1px solid var(--border);
  border-radius: 10px; padding: 3px 4px 3px 14px;
}
.input-wrap:focus-within { border-color: var(--primary); }
.input-wrap input {
  flex: 1; border: none; background: none; outline: none;
  color: var(--text); font-size: 14px; padding: 7px 0; font-family: inherit;
}
.input-wrap input::placeholder { color: var(--text-dim); }
.input-acts { display: flex; gap: 2px; }
.input-acts i {
  width: 32px; height: 32px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-muted); font-size: 18px; cursor: pointer;
}
.input-acts i:hover { background: var(--bg-elevated); color: var(--text); }
.input-acts .send { background: var(--primary); color: #fff; font-size: 15px; }
</style>
