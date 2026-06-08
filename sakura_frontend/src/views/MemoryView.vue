<template>
  <div class="memory-page">
    <div class="mem-nav">
      <div v-for="item in navItems" :key="item.id"
        :class="['mem-nav-item', { active: activeTab === item.id }]"
        @click="activeTab = item.id">
        <i :class="item.icon"></i> {{ item.label }}
      </div>
    </div>
    <div class="mem-content">
      <div class="mem-header">
        <div class="left"><div class="title">{{ currentTitle }}</div><div class="sub">{{ currentSub }}</div></div>
        <div class="actions"><i class="ri-add-line"></i></div>
      </div>

      <!-- 全部 -->
      <div v-show="activeTab === 'all'" class="mem-body">
        <input class="mem-search" placeholder="搜索记忆 ...">
        <div class="mem-list">
          <div v-for="m in memories" :key="m.id" class="mem-item">
            <span :class="['tag', m.type]">{{ typeLabel[m.type] }}</span>
            <span class="txt">{{ m.text }}</span>
            <span class="time">{{ m.time }}</span>
          </div>
        </div>
      </div>

      <!-- 偏好/事实/情感 -->
      <div v-show="['pref','fact','emo'].includes(activeTab)" class="mem-body">
        <div class="mem-list">
          <div v-for="m in filteredMemories" :key="m.id" class="mem-item">
            <span :class="['tag', m.type]">{{ typeLabel[m.type] }}</span>
            <span class="txt">{{ m.text }}</span>
            <span class="time">{{ m.time }}</span>
            <button class="del-btn"><i class="ri-close-line"></i></button>
          </div>
        </div>
      </div>

      <!-- 摘要 -->
      <div v-show="activeTab === 'summ'" class="mem-body">
        <div class="card"><h4>近期摘要</h4><p>用户最近在专注于前端重构项目，同时也在学习 C 语言。工作压力较大。</p><div class="muted" style="margin-top:8px">更新于 1 小时前</div></div>
        <div class="card"><h4>一周回顾</h4><p>本周共 247 条消息，最活跃晚上 9-11 点。</p></div>
      </div>

      <!-- 关系图 -->
      <div v-show="activeTab === 'graph'" class="mem-body">
        <div class="graph-container">
          <div class="node center">👤 用户</div>
          <div v-for="(n, i) in graphNodes" :key="i" class="node" :style="n.style">{{ n.label }}</div>
          <div class="graph-hint">知识图谱 · 拖拽可移动节点</div>
        </div>
      </div>

      <!-- 设置 -->
      <div v-show="activeTab === 'settings'" class="mem-body">
        <div class="card"><h4>向量记忆引擎</h4><div class="fld"><label>嵌入模型</label><select><option selected>paraphrase-multilingual-MiniLM-L12-v2</option></select></div><div class="fld"><label>状态</label><span style="color:var(--accent)">● 已加载</span></div></div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'

export default {
  setup() {
    const activeTab = ref('all')
    const typeLabel = { pref: '偏好', fact: '事实', emo: '情感' }
    const navItems = [
      { id: 'all', label: '全部', icon: 'ri-archive-line' },
      { id: 'pref', label: '偏好', icon: 'ri-heart-line' },
      { id: 'fact', label: '事实', icon: 'ri-question-line' },
      { id: 'emo', label: '情感', icon: 'ri-emotion-line' },
      { id: 'summ', label: '摘要', icon: 'ri-history-line' },
      { id: 'graph', label: '关系图', icon: 'ri-share-node-line' },
      { id: 'settings', label: '设置', icon: 'ri-settings-4-line' },
    ]
    const currentTitle = computed(() => navItems.find(n => n.id === activeTab.value)?.label || '记忆')
    const currentSub = computed(() => activeTab.value === 'all' ? '共 12 条' : '')

    const memories = ref([
      { id: 1, type: 'pref', text: '喜欢喝美式咖啡，不加糖', time: '3 天前' },
      { id: 2, type: 'fact', text: '在一家互联网公司做前端开发', time: '1 周前' },
      { id: 3, type: 'emo', text: '最近工作压力大，需要倾听多于建议', time: '昨天' },
      { id: 4, type: 'pref', text: '晚上 11 点后更容易聊深入的话题', time: '2 天前' },
    ])
    const filteredMemories = computed(() => memories.value.filter(m => {
      if (activeTab.value === 'pref') return m.type === 'pref'
      if (activeTab.value === 'fact') return m.type === 'fact'
      if (activeTab.value === 'emo') return m.type === 'emo'
      return true
    }))

    const graphNodes = [
      { label: '前端开发', style: 'top:15%;left:18%' },
      { label: '喝美式咖啡', style: 'top:10%;right:18%' },
      { label: '加班到很晚', style: 'bottom:20%;left:22%' },
      { label: '喜欢深夜聊天', style: 'bottom:15%;right:15%' },
      { label: '学 C 语言', style: 'top:40%;right:8%' },
    ]

    return { activeTab, typeLabel, navItems, currentTitle, currentSub, memories, filteredMemories, graphNodes }
  }
}
</script>

<style scoped>
.memory-page { display: flex; flex: 1; min-height: 0; }
.mem-nav { width: 180px; background: var(--bg-base); border-right: 1px solid var(--border); padding: 12px 8px; flex-shrink: 0; overflow-y: auto; }
.mem-nav-item { padding: 7px 10px; border-radius: 6px; font-size: 13px; color: var(--text-muted); cursor: pointer; display: flex; align-items: center; gap: 8px; }
.mem-nav-item i { font-size: 15px; width: 18px; }
.mem-nav-item:hover { background: var(--bg-elevated); color: var(--text); }
.mem-nav-item.active { background: var(--bg-elevated); color: var(--text); }
.mem-content { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.mem-header { padding: 10px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.mem-header .left { display: flex; align-items: center; gap: 10px; }
.mem-header .title { font-size: 15px; font-weight: 600; }
.mem-header .sub { font-size: 12px; color: var(--text-muted); }
.mem-header .actions { display: flex; gap: 6px; color: var(--text-muted); font-size: 18px; cursor: pointer; }
.mem-body { flex: 1; padding: 20px; overflow-y: auto; }
.mem-search { width: 100%; padding: 8px 12px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 13px; outline: none; margin-bottom: 16px; }
.mem-search:focus { border-color: var(--primary); }
.mem-list { display: flex; flex-direction: column; gap: 6px; }
.mem-item { background: var(--bg-card); border-radius: 8px; border: 1px solid var(--border); padding: 12px 14px; display: flex; align-items: center; gap: 10px; }
.mem-item .tag { font-size: 10px; padding: 2px 7px; border-radius: 4px; background: var(--primary-dim); color: var(--primary); flex-shrink: 0; }
.tag.fact { background: hsla(160,60%,50%,.15); color: var(--accent); }
.tag.emo { background: hsla(320,50%,55%,.15); color: hsl(320,50%,55%); }
.mem-item .txt { flex: 1; font-size: 13px; }
.mem-item .time { font-size: 10px; color: var(--text-dim); flex-shrink: 0; }
.mem-item .del-btn { color: var(--text-dim); cursor: pointer; font-size: 14px; border: none; background: none; }
.mem-item .del-btn:hover { color: hsl(0,65%,55%); }
.card { background: var(--bg-card); border-radius: 10px; border: 1px solid var(--border); padding: 16px; margin-bottom: 12px; }
.card h4 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.card p { font-size: 13px; color: var(--text-muted); line-height: 1.6; }
.muted { font-size: 11px; color: var(--text-dim); }
.graph-container { background: var(--bg-card); border-radius: 10px; border: 1px solid var(--border); padding: 32px; height: 300px; display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden; }
.graph-container .node { position: absolute; padding: 6px 14px; border-radius: 14px; font-size: 12px; }
.graph-container .node.center { background: var(--primary); color: #fff; font-weight: 600; }
.graph-container .node:not(.center) { background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-muted); }
.graph-hint { color: var(--text-dim); font-size: 12px; }
</style>
