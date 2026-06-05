<template>
  <div class="vault-panel">
    <div v-if="loading">加载中...</div>
    <template v-else>
      <!-- 原子事实 -->
      <div v-if="facts.length" class="vault-section">
        <h4>原子事实 ({{ facts.length }})</h4>
        <div v-for="item in facts.slice(0, showAll.facts ? 999 : 5)" :key="item.key" class="vault-item fact-item">
          <span class="vault-cat" :class="item.category">{{ catLabel(item.category) }}</span>
          <span class="vault-val">{{ item.text }}</span>
          <span class="vault-imp" :title="'重要性 ' + item.importance">{{ item.importance }}</span>
          <button class="vault-del" @click="removeItem('profile', item.key)" title="删除">✕</button>
        </div>
        <button v-if="facts.length > 5" class="vault-more" @click="showAll.facts = !showAll.facts">
          {{ showAll.facts ? '收起' : '展开全部 ' + facts.length + ' 条' }}
        </button>
      </div>

      <!-- 画像 -->
      <div v-if="profile.length" class="vault-section">
        <h4>关于你 ({{ profile.length }})</h4>
        <div v-for="item in profile.slice(0, showAll.profile ? 999 : 5)" :key="item.key" class="vault-item">
          <span class="vault-key">{{ item.label || profileLabel(item.key) }}</span>
          <span class="vault-val">{{ profileValue(item.value) }}</span>
          <button class="vault-del" @click="removeItem('profile', item.key)" title="删除">✕</button>
        </div>
        <button v-if="profile.length > 5" class="vault-more" @click="showAll.profile = !showAll.profile">
          {{ showAll.profile ? '收起' : '展开全部 ' + profile.length + ' 条' }}
        </button>
      </div>

      <!-- 实体 -->
      <div v-if="entities.length" class="vault-section">
        <h4>认识的实体 ({{ entities.length }})</h4>
        <div v-for="(e, i) in entities.slice(0, showAll.entities ? 999 : 5)" :key="i" class="vault-item">
          <span class="vault-cat" :class="e.type">{{ entityTypeLabel(e.type) }}</span>
          <span class="vault-val">{{ e.text }}</span>
          <span class="vault-cnt">{{ e.linked_count }}条关联</span>
        </div>
        <button v-if="entities.length > 5" class="vault-more" @click="showAll.entities = !showAll.entities">
          {{ showAll.entities ? '收起' : '展开全部 ' + entities.length + ' 条' }}
        </button>
      </div>

      <!-- 知识图谱 -->
      <div v-if="knowledge.length" class="vault-section">
        <h4>知识图谱 ({{ knowledge.length }})</h4>
        <div v-for="(k, i) in knowledge.slice(0, showAll.knowledge ? 999 : 5)" :key="i" class="vault-item kg-item">
          <span class="kg-subj">{{ k.subject }}</span>
          <span class="kg-pred">→{{ k.predicate }}→</span>
          <span class="kg-obj">{{ k.object }}</span>
          <span class="vault-cnt">{{ Math.round(k.confidence * 100) }}%</span>
        </div>
        <button v-if="knowledge.length > 5" class="vault-more" @click="showAll.knowledge = !showAll.knowledge">
          {{ showAll.knowledge ? '收起' : '展开全部 ' + knowledge.length + ' 条' }}
        </button>
      </div>

      <!-- 工作记忆 -->
      <div v-if="hasScratch" class="vault-section">
        <h4>当前状态</h4>
        <div v-if="scratch.currently" class="vault-item">
          <span class="vault-key">状态</span>
          <span class="vault-val">{{ scratch.currently }}</span>
        </div>
        <div v-if="scratch.mood" class="vault-item">
          <span class="vault-key">情绪</span>
          <span class="vault-val">{{ scratch.mood }}</span>
        </div>
        <div v-if="scratch.goal" class="vault-item">
          <span class="vault-key">目标</span>
          <span class="vault-val">{{ scratch.goal }}</span>
        </div>
      </div>

      <!-- 滚动摘要 -->
      <div v-if="rollingSummary" class="vault-section">
        <h4>对话摘要</h4>
        <div class="vault-item">
          <span class="vault-val">{{ rollingSummary }}</span>
        </div>
      </div>

      <!-- 关键信息 -->
      <div v-if="keypoints.length" class="vault-section">
        <h4>重要信息 ({{ keypoints.length }})</h4>
        <div v-for="(k, i) in keypoints.slice(0, showAll.keypoints ? 999 : 5)" :key="'kp'+i" class="vault-item">
          <span class="vault-val">{{ k }}</span>
        </div>
        <button v-if="keypoints.length > 5" class="vault-more" @click="showAll.keypoints = !showAll.keypoints">
          {{ showAll.keypoints ? '收起' : '展开全部 ' + keypoints.length + ' 条' }}
        </button>
      </div>

      <!-- 摘要 -->
      <div v-if="summaries.length" class="vault-section">
        <h4>对话摘要 ({{ summaries.length }})</h4>
        <div v-for="(s, i) in summaries.slice(0, showAll.summaries ? 999 : 5)" :key="'sum'+i" class="vault-item">
          <span class="vault-val">{{ s }}</span>
          <button class="vault-del" @click="removeItem('summary', s)" title="删除">✕</button>
        </div>
        <button v-if="summaries.length > 5" class="vault-more" @click="showAll.summaries = !showAll.summaries">
          {{ showAll.summaries ? '收起' : '展开全部 ' + summaries.length + ' 条' }}
        </button>
      </div>

      <div v-if="!facts.length && !profile.length && !entities.length && !knowledge.length && !keypoints.length && !summaries.length" class="empty-hint">
        {{ aiName }}还没有记住关于你的信息，多聊聊天吧
      </div>
    </template>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  props: { aiName: { type: String, default: '佐仓' } },
  data() {
    return {
      profile: [],
      facts: [],
      entities: [],
      knowledge: [],
      scratch: {},
      rollingSummary: '',
      keypoints: [],
      summaries: [],
      loading: true,
      showAll: { profile: false, facts: false, entities: false, knowledge: false, keypoints: false, summaries: false },
    }
  },
  computed: {
    hasScratch() {
      return this.scratch.currently || this.scratch.mood || this.scratch.goal
    },
  },
  async mounted() { await this.load() },
  methods: {
    async load() {
      this.loading = true
      try {
        const res = await api.get('/memory/vault')
        this.profile = res.data.profile || []
        this.facts = res.data.facts || []
        this.entities = res.data.entities || []
        this.knowledge = res.data.knowledge || []
        this.scratch = res.data.scratch || {}
        this.rollingSummary = res.data.rolling_summary || ''
        this.keypoints = res.data.keypoints || []
        this.summaries = res.data.summaries || []
      } catch (e) { console.error(e) }
      this.loading = false
    },
    async removeItem(type, key) {
      if (!confirm('确定删除该记忆？')) return
      try { await api.delete(`/memory/vault/${type}`, { params: { key } }); await this.load() } catch (e) { console.error(e) }
    },
    catLabel(cat) {
      const map = { bio: '基本', pref: '偏好', exp: '经历', social: '社交', work: '工作', psy: '心理', event: '事件', memory: '记忆', general: '其他' }
      return map[cat] || cat
    },
    profileLabel(key) {
      const map = {
        name: '名字', user_name: '称呼', city: '城市', gender: '性别', age: '年龄',
        occupation: '职业', hobby: '爱好', personality: '性格', language: '语言',
        user_student: '身份', user_habit_stay_up: '习惯', user_habit: '习惯',
      }
      if (map[key]) return map[key]
      // 去掉常见前缀
      return key.replace(/^user_/, '').replace(/_/g, ' ')
    },
    profileValue(val) {
      if (!val) return ''
      // 尝试解析 JSON
      try {
        const obj = JSON.parse(val)
        if (typeof obj === 'object' && obj !== null) {
          return obj.text || obj.value || obj.name || obj.summary || JSON.stringify(obj)
        }
      } catch (e) {}
      return val
    },
    entityTypeLabel(type) {
      const map = { PERSON: '人', PLACE: '地', ORG: '机构', THING: '物', PET: '宠物' }
      return map[type] || type
    },
  },
}
</script>

<style scoped>
.vault-panel { padding: 4px; font-size: 13px; }
.vault-section { margin-bottom: 12px; }
.vault-section h4 { font-size: 12px; color: var(--tc2); margin: 0 0 6px; }
.vault-item { display: flex; gap: 8px; align-items: baseline; padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,.03); }
.vault-key { color: var(--p); font-size: 11px; white-space: nowrap; min-width: 60px; }
.vault-val { flex: 1; color: var(--tc); font-size: 12px; }
.vault-del { background: none; border: none; color: #e74c3c; cursor: pointer; font-size: 11px; padding: 0 4px; opacity: .5; }
.vault-del:hover { opacity: 1; }
.vault-more { background: none; border: 1px solid rgba(255,255,255,.1); color: var(--tc2); cursor: pointer; font-size: 11px; padding: 4px 12px; border-radius: 4px; margin-top: 4px; display: block; width: 100%; }
.vault-more:hover { border-color: var(--p); color: var(--p); }
.empty-hint { color: var(--tc2); font-size: 12px; text-align: center; padding: 20px; }
.vault-cat { font-size: 10px; padding: 1px 5px; border-radius: 3px; white-space: nowrap; background: rgba(255,255,255,.06); color: var(--tc2); }
.vault-cat.bio { background: rgba(52,152,219,.15); color: #3498db; }
.vault-cat.pref { background: rgba(155,89,182,.15); color: #9b59b6; }
.vault-cat.exp { background: rgba(46,204,113,.15); color: #2ecc71; }
.vault-cat.social { background: rgba(241,196,15,.15); color: #f1c40f; }
.vault-cat.work { background: rgba(230,126,34,.15); color: #e67e22; }
.vault-cat.event { background: rgba(231,76,60,.15); color: #e74c3c; }
.vault-imp { font-size: 10px; color: var(--tc2); min-width: 16px; text-align: center; }
.vault-cnt { font-size: 10px; color: var(--tc2); white-space: nowrap; }
.kg-item { font-size: 12px; }
.kg-subj { color: var(--p); }
.kg-pred { color: var(--tc2); font-size: 11px; }
.kg-obj { color: var(--tc); }
</style>
