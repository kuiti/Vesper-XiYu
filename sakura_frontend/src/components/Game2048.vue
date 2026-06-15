<template>
  <div class="game-2048" tabindex="0" ref="board">
    <div class="g2048-header">
      <span class="g2048-score">得分: {{ score }}</span>
      <span class="g2048-best">最佳: {{ best }}</span>
      <button @click="newGame" class="g2048-new">新局</button>
    </div>
    <div class="g2048-grid">
      <div v-for="(v, i) in flat" :key="i" :class="['g2048-cell', 'tile-' + v]">{{ v || '' }}</div>
    </div>
    <div v-if="over" class="g2048-over">游戏结束!</div>
    <div class="g2048-hint">方向键控制</div>
    <button v-if="!over && score > 0 && !_helped" class="help-btn" @click="askHelp">向{{ aiName }}求助</button>
  </div>
</template>

<script>
import api from '../api'
export default {
  emits: ['ai-event', 'help'],
  props: { aiName: { type: String, default: '佐仓' } },
  data() {
    return { grid: [], score: 0, best: 0, over: false, _reached2048: false, _helped: false }
  },
  computed: {
    flat() { return this.grid.flat() }
  },
  mounted() {
    this.best = 0
    this.$refs.board?.focus()
    this.newGame()
    window.addEventListener('keydown', this._globalKey)
    api.get('/settings/').then(r => { if (r.data?.['2048_best']) this.best = parseInt(r.data['2048_best']) || 0 }).catch(() => {})
  },
  beforeUnmount() { window.removeEventListener('keydown', this._globalKey) },
  methods: {
    _globalKey(e) {
      if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.key) && document.activeElement?.closest('.game-2048')) {
        e.preventDefault(); this.onKey(e)
      }
    },
    newGame() {
      this.grid = Array(4).fill(null).map(() => Array(4).fill(0))
      this.score = 0; this.over = false; this._reached2048 = false
      this._spawn(); this._spawn()
    },
    _spawn() {
      const empty = []
      this.grid.forEach((r, y) => r.forEach((v, x) => { if (!v) empty.push({x, y}) }))
      if (!empty.length) return
      const {x, y} = empty[Math.floor(Math.random() * empty.length)]
      this.grid[y][x] = Math.random() < 0.9 ? 2 : 4
    },
    _slide(row) {
      let arr = row.filter(v => v)
      for (let i = 0; i < arr.length - 1; i++) {
        if (arr[i] === arr[i+1]) { arr[i] *= 2; this.score += arr[i]; arr[i+1] = 0 }
      }
      arr = arr.filter(v => v)
      while (arr.length < 4) arr.push(0)
      return arr
    },
    onKey(e) {
      if (this.over) return
      let moved = false
      const old = this.grid.map(r => [...r])
      const dir = { ArrowLeft: 'L', ArrowRight: 'R', ArrowUp: 'U', ArrowDown: 'D' }[e.key]
      if (!dir) return

      if (dir === 'L') this.grid = this.grid.map(r => this._slide(r))
      else if (dir === 'R') this.grid = this.grid.map(r => this._slide([...r].reverse()).reverse())
      else if (dir === 'U') {
        for (let x = 0; x < 4; x++) {
          const col = this._slide([this.grid[0][x], this.grid[1][x], this.grid[2][x], this.grid[3][x]])
          for (let y = 0; y < 4; y++) this.grid[y][x] = col[y]
        }
      } else if (dir === 'D') {
        for (let x = 0; x < 4; x++) {
          const col = this._slide([this.grid[3][x], this.grid[2][x], this.grid[1][x], this.grid[0][x]]).reverse()
          for (let y = 0; y < 4; y++) this.grid[y][x] = col[y]
        }
      }

      moved = JSON.stringify(old) !== JSON.stringify(this.grid)
      if (moved) {
        this._spawn()
        if (this.score > this.best) { this.best = this.score; api.post('/settings/', { key: '2048_best', value: this.best }).catch(() => {}) }
        // Check for 2048 tile
        if (this.grid.some(r => r.some(v => v === 2048)) && !this._reached2048) { this._reached2048 = true; this.$emit('ai-event', { type: 'reached_2048', score: this.score }) }
        // Check game over
        if (!this._canMove()) { this.over = true; this.$emit('ai-event', { type: 'game_over', score: this.score }) }
      }
    },
    askHelp() { this._helped = true; const s=this.score; this.newGame(); this.score=s; this.$emit('help', { score: s }) },
    _canMove() {
      for (let y = 0; y < 4; y++)
        for (let x = 0; x < 4; x++) {
          if (!this.grid[y][x]) return true
          if (x < 3 && this.grid[y][x] === this.grid[y][x+1]) return true
          if (y < 3 && this.grid[y][x] === this.grid[y+1][x]) return true
        }
      return false
    }
  }
}
</script>

<style scoped>
.game-2048 { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 10px; outline: none; }
.g2048-header { display: flex; align-items: center; gap: 12px; color: var(--text-primary); font-size: 13px; }
.g2048-score { font-weight: 600; }
.g2048-best { color: var(--text-secondary); }
.g2048-new { background: var(--accent-primary); border: none; color: #fff; border-radius: 4px; padding: 4px 12px; cursor: pointer; font-size: 12px; }
.g2048-grid { display: grid; grid-template-columns: repeat(4, 60px); gap: 4px; background: var(--border-default); padding: 4px; border-radius: 6px; }
.g2048-cell { width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; font-size: 22px; font-weight: 700; border-radius: 4px; background: var(--surface-sidebar); color: var(--text-primary); transition: all .12s ease; will-change: transform; }
.g2048-cell.tile-pop { animation: tilePop .18s ease; }
@keyframes tilePop { 0% { transform: scale(0); opacity: 0; } 60% { transform: scale(1.15); } 100% { transform: scale(1); opacity: 1; } }
.tile-2 { background: rgba(255,255,255,.06); }
.tile-4 { background: rgba(255,255,255,.08); }
.tile-8 { background: #e8929b; color: #fff; }
.tile-16 { background: #e87461; color: #fff; }
.tile-32 { background: #e85d3a; color: #fff; }
.tile-64 { background: #e8451a; color: #fff; }
.tile-128 { background: #f1c40f; color: #fff; font-size: 20px; }
.tile-256 { background: #f39c12; color: #fff; font-size: 20px; }
.tile-512 { background: #e67e22; color: #fff; font-size: 18px; }
.tile-1024 { background: #d35400; color: #fff; font-size: 16px; }
.tile-2048 { background: #e74c3c; color: #fff; font-size: 16px; }
.tile-4096, .tile-8192 { background: #2ecc71; color: #fff; font-size: 14px; }
.g2048-over { position: absolute; margin-top: 100px; color: #e74c3c; font-weight: 700; font-size: 16px; background: rgba(0,0,0,.7); padding: 4px 12px; border-radius: 4px; }
.g2048-hint { color: var(--text-secondary); font-size: 11px; }
.help-btn { background: var(--accent-primary); border: none; color: #fff; border-radius: 6px; padding: 4px 12px; cursor: pointer; font-size: 12px; margin-top: 4px; }
</style>
