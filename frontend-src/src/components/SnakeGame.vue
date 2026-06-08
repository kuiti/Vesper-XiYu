<template>
  <div class="snake-game">
    <div class="snake-header">
      <span>贪吃蛇</span>
      <span class="snake-score">得分: {{ score }}</span>
    </div>
    <canvas ref="canvas" :width="canvasW" :height="canvasH" class="snake-canvas"></canvas>
    <div class="snake-controls">
      <button @click="startGame" v-if="!playing">{{ gameOver ? '再来一局' : '开始游戏' }}</button>
      <span v-if="gameOver" class="snake-over">游戏结束!</span>
    </div>
    <div class="snake-hint">方向键控制 · 空格暂停</div>
    <button v-if="playing && !_helped" class="help-btn" @click="askHelp">向{{ aiName }}求助</button>
  </div>
</template>

<script>
import api from '../api.js'
const GS = 20, COLS = 18, ROWS = 18

export default {
  emits: ['ai-event', 'help'],
  props: { aiName: { type: String, default: '夕语' } },
  data() {
    return {
      snake: [{x:8,y:8},{x:7,y:8},{x:6,y:8}],
      food: {x:12,y:8},
      dir: {x:1,y:0},
      nextDir: {x:1,y:0},
      score: 0, highScore: 0, playing: false, gameOver: false,
      _timer: null, _paused: false, _helped: false
    }
  },
  computed: {
    canvasW() { return GS * COLS },
    canvasH() { return GS * ROWS }
  },
  mounted() {
    window.addEventListener('keydown', this._onKey)
    api.get('/settings/').then(r => { if (r.data?.snake_high) this.highScore = parseInt(r.data.snake_high) || 0 }).catch(() => {})
    this._draw()
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this._onKey)
    if (this._timer) clearInterval(this._timer)
  },
  methods: {
    startGame() {
      this.snake = [{x:8,y:8},{x:7,y:8},{x:6,y:8}]
      this.dir = {x:1,y:0}; this.nextDir = {x:1,y:0}
      this.score = 0; this.gameOver = false; this.playing = true; this._paused = false
      this._placeFood()
      if (this._timer) clearInterval(this._timer)
      this._speed = 100
      this._timer = setInterval(() => this._tick(), this._speed)
    },
    _tick() {
      if (this._paused || !this.playing) return
      this.dir = {...this.nextDir}
      const head = {x: this.snake[0].x + this.dir.x, y: this.snake[0].y + this.dir.y}
      if (head.x < 0) head.x = COLS - 1; if (head.x >= COLS) head.x = 0; if (head.y < 0) head.y = ROWS - 1; if (head.y >= ROWS) head.y = 0
      if (this.snake.some(s => s.x === head.x && s.y === head.y)) return this._die()
      this.snake.unshift(head)
      if (head.x === this.food.x && head.y === this.food.y) {
        this.score += this._foodScore || 10
        if (this._foodScore >= 50) { if (this.snake.length > 2) this.snake.pop() }
        this._placeFood()
        if (this._speed > 50) { this._speed -= 2; clearInterval(this._timer); this._timer = setInterval(() => this._tick(), this._speed) }
      } else {
        this.snake.pop()
      }
      this._draw()
    },
    _placeFood() {
      if (this.snake.length >= COLS * ROWS) return
      do { this.food = {x: Math.floor(Math.random() * COLS), y: Math.floor(Math.random() * ROWS)} }
      while (this.snake.some(s => s.x === this.food.x && s.y === this.food.y))
      const r = Math.random()
      if (r < 0.05) { this._foodScore = 50; this._foodColor = '#ff00ff' }
      else if (r < 0.20) { this._foodScore = 30; this._foodColor = '#ffd700' }
      else { this._foodScore = 10; this._foodColor = '#ff6b6b' }
    },
    _die() {
      this.playing = false; this.gameOver = true
      if (this._timer) { clearInterval(this._timer); this._timer = null }
      if (this.score > this.highScore) {
        this.highScore = this.score
        api.post('/settings/', { key: 'snake_high', value: this.score }).catch(() => {})
        this.$emit('ai-event', { type: 'high_score', score: this.score })
      } else if (this.score > 50) {
        this.$emit('ai-event', { type: 'game_over', score: this.score })
      }
      this._draw()
    },
    _draw() {
      const c = this.$refs.canvas; if (!c) return
      const ctx = c.getContext('2d')
      ctx.fillStyle = '#0f1119'; ctx.fillRect(0, 0, this.canvasW, this.canvasH)
      // Grid
      ctx.strokeStyle = 'rgba(255,255,255,.03)'; ctx.lineWidth = .5
      for (let x = 0; x <= COLS; x++) { ctx.beginPath(); ctx.moveTo(x*GS, 0); ctx.lineTo(x*GS, this.canvasH); ctx.stroke() }
      for (let y = 0; y <= ROWS; y++) { ctx.beginPath(); ctx.moveTo(0, y*GS); ctx.lineTo(this.canvasW, y*GS); ctx.stroke() }
      // Food with pulse
      const pulse = 1 + 0.1 * Math.sin(Date.now() / 200)
      ctx.fillStyle = this._foodColor || '#ff6b6b'; ctx.beginPath(); ctx.arc(this.food.x*GS+GS/2, this.food.y*GS+GS/2, (GS/2-2)*pulse, 0, Math.PI*2); ctx.fill()
      ctx.fillStyle = 'rgba(255,107,107,.3)'; ctx.beginPath(); ctx.arc(this.food.x*GS+GS/2, this.food.y*GS+GS/2, GS/2, 0, Math.PI*2); ctx.fill()
      // Snake with rounded segments
      this.snake.forEach((s, i) => {
        const alpha = 1 - i * 0.04
        ctx.fillStyle = i === 0 ? '#8cc8ff' : `rgba(106,159,216,${alpha})`
        const r = GS/2 - 1.5
        ctx.beginPath()
        ctx.roundRect(s.x*GS + 1.5, s.y*GS + 1.5, GS - 3, GS - 3, r * (i === 0 ? 1 : 0.6))
        ctx.fill()
        // Head glow
        if (i === 0) {
          ctx.fillStyle = 'rgba(140,200,255,.3)'
          ctx.beginPath(); ctx.arc(s.x*GS+GS/2, s.y*GS+GS/2, GS/2+2, 0, Math.PI*2); ctx.fill()
        }
      })
      if (!this.playing && this.gameOver) {
        ctx.fillStyle = 'rgba(0,0,0,.5)'; ctx.fillRect(0, 0, this.canvasW, this.canvasH)
        ctx.fillStyle = '#e2e8f0'; ctx.font = '18px monospace'; ctx.textAlign = 'center'
        ctx.fillText('游戏结束', this.canvasW/2, this.canvasH/2)
        ctx.font = '12px monospace'; ctx.fillText('最高分: ' + this.highScore, this.canvasW/2, this.canvasH/2 + 24)
      }
    },
    askHelp() { this._helped = true; const s=this.score; this.startGame(); this.score=s; this.$emit('help', { score: s }) },
    _onKey(e) {
      const d = {ArrowUp:{x:0,y:-1},ArrowDown:{x:0,y:1},ArrowLeft:{x:-1,y:0},ArrowRight:{x:1,y:0}}
      if (d[e.key]) { e.preventDefault(); const nd = d[e.key]; if (nd.x !== -this.dir.x || nd.y !== -this.dir.y) this.nextDir = nd }
      if (e.key === ' ') { e.preventDefault(); this._paused = !this._paused }
    }
  }
}
</script>

<style scoped>
.snake-game { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 12px; }
.snake-header { display: flex; justify-content: space-between; width: 100%; max-width: 360px; color: var(--tc); font-size: 14px; }
.snake-score { color: var(--p); font-weight: 600; }
.snake-canvas { border: 1px solid var(--border); border-radius: 6px; }
.snake-controls button { background: var(--p); border: none; color: #fff; border-radius: 6px; padding: 8px 24px; cursor: pointer; font-size: 14px; }
.snake-over { color: #e74c3c; font-weight: 600; }
.snake-hint { color: var(--tc2); font-size: 11px; }
.help-btn { background: var(--p); border: none; color: #fff; border-radius: 6px; padding: 4px 12px; cursor: pointer; font-size: 12px; margin-top: 4px; }
</style>
