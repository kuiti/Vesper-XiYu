<template>
  <div class="mem-graph">
    <svg :viewBox="`0 0 ${w} ${h}`" ref="svg">
      <!-- 连线 -->
      <line v-for="l in links" :key="l.key" :x1="l.x1" :y1="l.y1" :x2="l.x2" :y2="l.y2" :stroke="l.color" stroke-width="1" opacity=".4"/>
      <!-- 节点 -->
      <g v-for="n in nodes" :key="n.key" :transform="`translate(${n.x},${n.y})`">
        <circle r="6" :fill="n.color"/>
        <text :x="n.labelX" :y="5" :text-anchor="n.anchor" font-size="10" :fill="n.color">{{ n.label }}</text>
      </g>
    </svg>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  props: { aiName: { type: String, default: '佐仓' } },
  data() { return { w: 300, h: 250, nodes: [], links: [], _unmounted: false } },
  async mounted() {
    try {
      const vaultRes = await api.get('/memory/vault')
      if (this._unmounted) return
      const profile = vaultRes.data.profile || []
      const cx = this.w / 2; const cy = this.h / 2
      // 中心节点：用户
      const nodes = [{ key: 'user', label: '我', x: cx, y: cy, color: '#e8929b', labelX: 10, anchor: 'start' }]
      // AI节点
      nodes.push({ key: 'ai', label: this.aiName, x: cx, y: cy - 60, color: '#5390d4', labelX: 10, anchor: 'start' })
      const links = []
      links.push({ key: 'rel', x1: cx, y1: cy, x2: cx, y2: cy - 54, color: '#c9b037' })
      // 画像节点环状排列
      const colors = ['#2ea043', '#bf8700', '#8250df', '#cf222e', '#0550ae', '#1a7f37']
      const sliced = profile.slice(0, 10)
      sliced.forEach((p, i) => {
        const angle = (i / Math.max(sliced.length, 1)) * Math.PI * 2
        const r = 70
        const x = cx + Math.cos(angle) * r
        const y = cy + Math.sin(angle) * r
        const label = p.label || this.graphLabel(p.key)
        nodes.push({ key: p.key, label, x, y, color: colors[i % colors.length], labelX: 8, anchor: 'start' })
        links.push({ key: p.key, x1: cx, y1: cy, x2: x, y2: y, color: colors[i % colors.length] })
      })
      if (!this._unmounted) { this.nodes = nodes; this.links = links }
    } catch (e) { console.error(e) }
  },
  beforeUnmount() { this._unmounted = true },
  methods: {
    graphLabel(key) {
      const map = { user_student: '学生', user_habit_stay_up: '熬夜', user_habit: '习惯',
        name: '名字', user_name: '称呼', city: '城市', gender: '性别', age: '年龄',
        occupation: '职业', hobby: '爱好', personality: '性格',
      }
      if (map[key]) return map[key]
      const clean = key.replace(/^user_/, '').replace(/_/g, ' ')
      return clean.length > 6 ? clean.slice(0, 5) + '..' : clean
    }
  }
}
</script>

<style scoped>
.mem-graph { overflow: hidden; }
.mem-graph svg { width: 100%; height: auto; }
</style>
