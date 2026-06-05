<template>
  <div class="emotion-panel">
    <!-- Tab bar -->
    <div class="ep-tabs">
      <button v-for="t in tabs" :key="t.key" :class="{ active: activeTab === t.key }" @click="activeTab = t.key">
        {{ t.label }}
      </button>
    </div>

    <!-- Tab 1: 关系曲线 -->
    <div v-if="activeTab === 'curve'" class="ep-tab">
      <div class="ep-loading" v-if="loading.curve">加载中...</div>
      <div class="ep-error" v-else-if="error.curve">加载失败，请重试</div>
      <div v-else>
        <div class="ep-curve-box">
          <div class="curve-hint">❤️ 好感 {{ relationship.affection }}/100 &nbsp; 🔒 信任 {{ relationship.trust }}/100</div>

          <!-- 图1：好感度趋势（0-100 固定Y轴） -->
          <div class="curve-section">
            <div class="curve-title"><span class="dot red"></span> 好感度趋势（近14天）</div>
            <div class="curve-chart">
              <svg :width="chartWidth + 30" :height="chartHeight">
                <line x1="30" y1="0" x2="310" y2="0" stroke="var(--border)" />
                <line x1="30" y1="120" x2="310" y2="120" stroke="var(--border)" />
                <line x1="30" y1="60" x2="310" y2="60" stroke="var(--border)" stroke-dasharray="2" />
                <template v-for="i in [-100,-50,0,50,100]" :key="'al'+i">
                  <line :x1="30" :y1="chartHeight-((i+100)/200*chartHeight)" :x2="chartWidth+30" :y2="chartHeight-((i+100)/200*chartHeight)" stroke="var(--border)" stroke-dasharray="4" />
                  <text :x="5" :y="chartHeight-((i+100)/200*chartHeight) + 4" fill="var(--tc2)" font-size="10" font-family="monospace">{{ i }}</text>
                </template>
                <polyline :points="affectionPoints" fill="none" stroke="#f0a0b0" stroke-width="2" />
                <circle v-for="(p, idx) in affectionDots" :key="'ad'+idx" :cx="p.x" :cy="p.y" r="5" fill="#f0a0b0" class="hover-dot">
                  <title>{{ p.date }}: 好感 {{ p.val }}</title>
                </circle>
              </svg>
            </div>
          </div>

          <!-- 图2：信任度趋势（0-100 固定Y轴） -->
          <div class="curve-section">
            <div class="curve-title"><span class="dot blue"></span> 信任度趋势（近14天）</div>
            <div class="curve-chart">
              <svg :width="chartWidth + 30" :height="chartHeight">
                <template v-for="i in [-100,-50,0,50,100]" :key="'tl'+i">
                  <line :x1="30" :y1="chartHeight-((i+100)/200*chartHeight)" :x2="chartWidth+30" :y2="chartHeight-((i+100)/200*chartHeight)" stroke="var(--border)" stroke-dasharray="4" />
                  <text :x="5" :y="chartHeight-((i+100)/200*chartHeight) + 4" fill="var(--tc2)" font-size="10" font-family="monospace">{{ i }}</text>
                </template>
                <polyline :points="trustPoints" fill="none" stroke="#5390d4" stroke-width="2" />
                <circle v-for="(p, idx) in trustDots" :key="'td'+idx" :cx="p.x" :cy="p.y" r="5" fill="#5390d4" class="hover-dot">
                  <title>{{ p.date }}: 信任 {{ p.val }}</title>
                </circle>
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 2: 情绪日历 -->
    <div v-if="activeTab === 'calendar'" class="ep-tab">
      <div class="ep-loading" v-if="loading.calendar">加载中...</div>
      <div class="ep-error" v-else-if="error.calendar">加载失败，请重试</div>
      <div v-else class="ep-calendar">
        <div class="cal-row" v-for="week in calendarWeeks" :key="'w'+week[0].date">
          <div v-for="day in week" :key="day.date" class="cal-day" :class="day.class" :title="day.tooltip">
            {{ day.dayNum }}
          </div>
        </div>
        <div class="cal-legend">
          <span>负面</span>
          <span class="cal-swatch s-1"></span><span class="cal-swatch s-2"></span><span class="cal-swatch s-3"></span><span class="cal-swatch s-4"></span><span class="cal-swatch s-5"></span>
          <span>正面</span>
        </div>
      </div>
    </div>

    <!-- Tab 3: 心路历程 -->
    <div v-if="activeTab === 'timeline'" class="ep-tab">
      <div class="ep-loading" v-if="loading.timeline">加载中...</div>
      <div class="ep-error" v-else-if="error.timeline">加载失败，请重试</div>
      <div v-else-if="!events.length" class="ep-empty">还没有情感事件记录，多聊几句就会有啦。</div>
      <div v-else class="ep-timeline">
        <div v-for="ev in events" :key="ev.id" class="tl-item">
          <div class="tl-dot" :class="eventClass(ev.event_type)"></div>
          <div class="tl-time">{{ formatDate(ev.timestamp) }}</div>
          <div class="tl-body">
            <span class="tl-reason">{{ ev.reason }}</span>
            <span class="tl-deltas">
              <span v-if="ev.affection_delta" :class="ev.affection_delta > 0 ? 'delta-pos' : 'delta-neg'">
                好感{{ ev.affection_delta > 0 ? '+' : '' }}{{ ev.affection_delta.toFixed(1) }}
              </span>
              <span v-if="ev.trust_delta" :class="ev.trust_delta > 0 ? 'delta-pos' : 'delta-neg'">
                信任{{ ev.trust_delta > 0 ? '+' : '' }}{{ ev.trust_delta.toFixed(1) }}
              </span>
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 4: AI 性格画像 -->
    <div v-if="activeTab === 'portrait'" class="ep-tab">
      <div class="ep-loading" v-if="loading.portrait">加载中...</div>
      <div class="ep-error" v-else-if="error.portrait">加载失败，请重试</div>
      <div v-else class="ep-portrait">
        <div class="portrait-radar">
          <div class="radar-item" v-for="(val, key) in profile.traits" :key="key">
            <div class="radar-label">{{ traitLabel(key) }}</div>
            <div class="radar-bar-wrap">
              <div class="radar-bar" :style="{ width: (val*100)+'%', background: traitColor(key) }"></div>
            </div>
            <div class="radar-val">{{ (val*100).toFixed(0) }}</div>
          </div>
        </div>
        <div class="portrait-summary">{{ profile.summary }}</div>
        <div class="portrait-desc">
          <div v-for="(desc, key) in profile.descriptions" :key="key" class="desc-item">
            <strong>{{ traitLabel(key) }}</strong>：{{ desc }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  name: 'EmotionPanel',
  data() {
    return {
      activeTab: 'curve',
      tabs: [
        { key: 'curve', label: '关系曲线' },
        { key: 'calendar', label: '情绪日历' },
        { key: 'timeline', label: '心路历程' },
        { key: 'portrait', label: 'AI性格' }
      ],
      loading: { curve: true, calendar: true, timeline: true, portrait: true },
      error: { curve: false, calendar: false, timeline: false, portrait: false },
      relationship: { affection: 30, trust: 30 },
      dailyEmotion: [],
      affectionHistory: [],
      trustHistory: [],
      events: [],
      profile: { traits: {}, descriptions: {}, summary: '' },
      chartWidth: 280,
      chartHeight: 120
    }
  },
  computed: {
    // 好感趋势：-100到100 Y轴
    affectionPoints() {
      const w = this.chartWidth, h = this.chartHeight
      const pts = this.affectionHistory.slice(-14)
      if (!pts.length) return `30,${h/2} ${w+30},${h/2}`
      return pts.map((d, i) => {
        const x = 30 + (i / Math.max(pts.length - 1, 1)) * w
        const norm = (d.value + 100) / 200
        const y = h - norm * h
        return `${x.toFixed(0)},${y.toFixed(0)}`
      }).join(' ')
    },
    trustPoints() {
      const w = this.chartWidth, h = this.chartHeight
      const pts = this.trustHistory.slice(-14)
      if (!pts.length) return `30,${h/2} ${w+30},${h/2}`
      return pts.map((d, i) => {
        const x = 30 + (i / Math.max(pts.length - 1, 1)) * w
        const norm = (d.value + 100) / 200
        const y = h - norm * h
        return `${x.toFixed(0)},${y.toFixed(0)}`
      }).join(' ')
    },
    affectionDots() {
      const w = this.chartWidth, h = this.chartHeight
      return this.affectionHistory.slice(-14).map((d, i) => {
        const x = 30 + (i / Math.max(this.affectionHistory.slice(-14).length - 1, 1)) * w
        const norm = (d.value + 100) / 200
        return { x, y: h - norm * h, val: d.value, date: d.date }
      })
    },
    trustDots() {
      const w = this.chartWidth, h = this.chartHeight
      return this.trustHistory.slice(-14).map((d, i) => {
        const x = 30 + (i / Math.max(this.trustHistory.slice(-14).length - 1, 1)) * w
        const norm = (d.value + 100) / 200
        return { x, y: h - norm * h, val: d.value, date: d.date }
      })
    },
    calendarWeeks() {
      if (!this.dailyEmotion.length) return []
      const days = this.dailyEmotion.slice(-28)
      const weeks = []
      let week = []
      // pad start to align with weekday
      const firstDate = new Date(days[0].date)
      const startDow = firstDate.getDay()
      for (let i = 0; i < startDow; i++) week.push({ date: 'pad'+i, dayNum: '', score: 0, class: '', tooltip: '' })
      days.forEach(d => {
        const dt = new Date(d.date)
        week.push({
          date: d.date,
          dayNum: dt.getDate(),
          score: d.score,
          class: this.scoreClass(d.score),
          tooltip: `${d.date} 评分:${(d.score || 0).toFixed(1)} 消息:${d.total_messages}`
        })
        if (week.length === 7) { weeks.push(week); week = [] }
      })
      if (week.length) weeks.push(week)
      return weeks
    }
  },
  mounted() {
    this.loadAll()
  },
  methods: {
    async loadAll() {
      await Promise.all([
        this.loadRelationship(),
        this.loadTimeline(),
        this.loadProfile(),
        this.loadEvents()
      ])
    },
    async loadRelationship() {
      try {
        const { data } = await api.get('/emotion/relationship')
        this.relationship = data
      } catch (e) { this.error.curve = true; console.error('load relationship failed', e) }
      this.loading.curve = false
    },
    async loadTimeline() {
      try {
        const { data } = await api.get('/emotion/timeline?days=28')
        this.dailyEmotion = data.daily_emotion || []
        this.affectionHistory = data.affection_history || []
        this.trustHistory = data.trust_history || []
      } catch (e) { this.error.calendar = true; console.error('load timeline failed', e) }
      this.loading.calendar = false
    },
    async loadProfile() {
      try {
        const { data } = await api.get('/emotion/profile')
        this.profile = data
      } catch (e) { this.error.portrait = true; console.error('load profile failed', e) }
      this.loading.portrait = false
    },
    async loadEvents() {
      try {
        const { data } = await api.get('/emotion/events?limit=50')
        this.events = data.events || []
      } catch (e) { this.error.timeline = true; console.error('load events failed', e) }
      this.loading.timeline = false
    },
    eventClass(type) {
      if (!type) return ''
      if (type.includes('thanks') || type.includes('positive')) return 'dot-good'
      if (type.includes('angry') || type.includes('negative') || type.includes('lie')) return 'dot-bad'
      if (type.includes('decay') || type.includes('adapt')) return 'dot-auto'
      return 'dot-neutral'
    },
    formatDate(ts) {
      if (!ts) return ''
      const d = new Date(ts)
      return `${d.getMonth()+1}/${d.getDate()} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
    },
    scoreClass(score) {
      if (score > 5) return 's-5'
      if (score > 2) return 's-4'
      if (score > -2) return 's-3'
      if (score > -5) return 's-2'
      return 's-1'
    },
    traitLabel(key) {
      const map = { openness: '开放性', conscientiousness: '尽责性', extraversion: '外向性', agreeableness: '宜人性', neuroticism: '神经质' }
      return map[key] || key
    },
    traitColor(key) {
      const map = { openness: '#f39c12', conscientiousness: '#2ecc71', extraversion: '#3498db', agreeableness: '#9b59b6', neuroticism: '#e74c3c' }
      return map[key] || '#888'
    }
  }
}
</script>

<style scoped>
.emotion-panel { min-height: 300px; color: #ecf0f1; }
.ep-tabs { display: flex; gap: 4px; margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,.06); padding-bottom: 8px; }
.ep-tabs button { border: none; background: none; padding: 5px 14px; border-radius: 6px; cursor: pointer; color: #7f8c8d; font-size: 13px; }
.ep-tabs button.active { background: var(--p); color: #fff; }
.ep-tab { min-height: 200px; }
.ep-loading, .ep-empty { text-align: center; color: #7f8c8d; padding: 40px 0; font-size: 13px; }

/* Curve */
.ep-curve-box { text-align: center; }
.curve-hint { font-size: 13px; color: #7f8c8d; margin-bottom: 12px; }
.curve-section { margin-bottom: 16px; }
.curve-title { font-size: 12px; color: var(--tc2); margin-bottom: 6px; display: flex; align-items: center; justify-content: center; gap: 4px; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin: 0 2px; }
.dot.red { background: #c0392b; }
.dot.blue { background: #5b9bd5; }
.curve-chart { overflow: hidden; display: flex; justify-content: center; }
.hover-dot { cursor: pointer; transition: r .15s; }
.hover-dot:hover { r: 7; }

/* Calendar */
.ep-calendar { text-align: center; }
.cal-row { display: flex; justify-content: center; gap: 3px; margin-bottom: 3px; }
.cal-day { width: 28px; height: 28px; border-radius: 4px; font-size: 12px; display: flex; align-items: center; justify-content: center; color: #7f8c8d; background: rgba(255,255,255,.04); }
.cal-day.s-1 { background: #78281f; color: #ecf0f1; }
.cal-day.s-2 { background: #7d5a1a; color: #ecf0f1; }
.cal-day.s-3 { background: rgba(255,255,255,.04); }
.cal-day.s-4 { background: #2c5f7a; color: #ecf0f1; }
.cal-day.s-5 { background: #1e6b3b; color: #ecf0f1; }
.cal-legend { display: flex; align-items: center; justify-content: center; gap: 4px; margin-top: 8px; font-size: 12px; color: #7f8c8d; }
.cal-swatch { display: inline-block; width: 14px; height: 14px; border-radius: 3px; }
.cal-swatch.s-1 { background: #78281f; } .cal-swatch.s-2 { background: #7d5a1a; } .cal-swatch.s-3 { background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); } .cal-swatch.s-4 { background: #2c5f7a; } .cal-swatch.s-5 { background: #1e6b3b; }

/* Timeline */
.ep-timeline { max-height: 340px; overflow-y: auto; }
.tl-item { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,.06); align-items: flex-start; }
.tl-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
.tl-dot.dot-good { background: #4a9; }
.tl-dot.dot-bad { background: #c0392b; }
.tl-dot.dot-auto { background: #b8860b; }
.tl-dot.dot-neutral { background: #7f8c8d; }
.tl-time { font-size: 12px; color: #7f8c8d; flex-shrink: 0; min-width: 55px; }
.tl-body { flex: 1; min-width: 0; }
.tl-reason { font-size: 13px; display: block; color: #ecf0f1; }
.tl-deltas { display: flex; gap: 8px; margin-top: 2px; font-size: 12px; }
.delta-pos { color: #4a9; }
.delta-neg { color: #c0392b; }

/* Portrait */
.ep-portrait { }
.portrait-radar { margin-bottom: 16px; }
.radar-item { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.radar-label { width: 54px; text-align: right; font-size: 13px; color: #7f8c8d; }
.radar-bar-wrap { flex: 1; height: 14px; background: rgba(255,255,255,.04); border-radius: 7px; overflow: hidden; }
.radar-bar { height: 100%; border-radius: 7px; transition: width 0.3s; min-width: 2px; }
.radar-val { width: 32px; font-size: 13px; font-weight: bold; color: #ecf0f1; }
.portrait-summary { padding: 10px 14px; background: rgba(255,255,255,.04); border-radius: 6px; margin-bottom: 12px; font-size: 14px; line-height: 1.6; color: #ecf0f1; }
.portrait-desc { display: flex; flex-direction: column; gap: 6px; }
.desc-item { font-size: 13px; color: #7f8c8d; line-height: 1.5; }
.desc-item strong { color: #ecf0f1; }
</style>
