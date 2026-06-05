<template>
  <div class="minesweeper">
    <div class="ms-header">
      <span class="ms-counter">雷 {{ mineCount - flags }}</span>
      <button class="ms-face" @click="newGame(difficulty)" @mousedown="facePressed = true" @mouseup="facePressed = false" @mouseleave="facePressed = false">
        {{ faceEmoji }}
      </button>
      <span class="ms-timer">{{ timerDisplay }}</span>
      <select v-model="difficulty" @change="newGame(difficulty)" class="ms-diff">
        <option value="easy">简单</option>
        <option value="medium">中等</option>
        <option value="hard">困难</option>
      </select>
    </div>
    <div class="ms-grid" :style="gridStyle">
      <div v-for="(cell, idx) in cells" :key="idx"
        :class="cellClass(cell)" @click="cellClick(idx)" @contextmenu.prevent="flag(idx)">
        {{ cellText(cell) }}
      </div>
    </div>
    <div v-if="won" class="ms-msg win">你赢了!</div>
    <div v-if="lost" class="ms-msg lose">踩雷了!</div>
    <button v-if="!won && !lost && started && !_helped" class="help-btn" @click="askHelp">向{{ aiName }}求助</button>
  </div>
</template>

<script>
import api from '../api.js'
const CFG = { easy: { w:9, h:9, m:10 }, medium: { w:16, h:16, m:40 }, hard: { w:30, h:16, m:99 } }

export default {
  emits: ['ai-event', 'help'],
  props: { aiName: { type: String, default: '佐仓' } },
  data() {
    const cfg = CFG.easy
    return {
      difficulty: 'easy',
      w: cfg.w, h: cfg.h, mineCount: cfg.m,
      cells: [], flags: 0, won: false, lost: false, started: false, mineWins: 0,
      timer: 0, facePressed: false, _timerInterval: null, _firstClick: true, _helped: false
    }
  },
  computed: {
    gridStyle() { return { gridTemplateColumns: `repeat(${this.w}, 22px)` } },
    faceEmoji() { if (this.lost) return ':('; if (this.won) return 'B)'; if (this.facePressed) return ':O'; return ':)' },
    timerDisplay() { return String(Math.min(this.timer, 999)).padStart(3, '0') }
  },
  mounted() { this.newGame('easy'); api.get('/settings/').then(r => { if (r.data?.minesweeper_wins) this.mineWins = parseInt(r.data.minesweeper_wins) || 0 }).catch(() => {}) },
  beforeUnmount() { if (this._timerInterval) { clearInterval(this._timerInterval); this._timerInterval = null } },
  methods: {
    newGame(d) {
      const cfg = CFG[d]; this.difficulty = d; this.w = cfg.w; this.h = cfg.h; this.mineCount = cfg.m
      this.flags = 0; this.won = false; this.lost = false; this.started = false; this.timer = 0; this.facePressed = false; this._helped = false
      this._firstClick = true
      if (this._timerInterval) { clearInterval(this._timerInterval); this._timerInterval = null }
      const total = cfg.w * cfg.h
      this.cells = Array.from({ length: total }, () => ({ mine: false, revealed: false, flagged: false, count: 0 }))
    },
    _startTimer() {
      if (this._timerInterval) return
      this.started = true
      this._timerInterval = setInterval(() => { if (!this.won && !this.lost) this.timer++ }, 1000)
    },
    _placeMines(safeIdx) {
      const total = this.w * this.h
      const safe = new Set([safeIdx])
      const dirs = [-1, 1, -this.w, this.w, -this.w-1, -this.w+1, this.w-1, this.w+1]
      for (const d of dirs) { const ni = safeIdx + d; if (ni >= 0 && ni < total && Math.abs((ni % this.w) - (safeIdx % this.w)) <= 1) safe.add(ni) }
      const mines = new Set()
      while (mines.size < this.mineCount) {
        const p = Math.floor(Math.random() * total)
        if (!safe.has(p)) mines.add(p)
      }
      for (const mi of mines) this.cells[mi].mine = true
      for (let i = 0; i < total; i++) {
        if (!this.cells[i].mine) {
          let c = 0
          for (const d of dirs) { const ni = i + d; if (ni >= 0 && ni < total && Math.abs((ni % this.w) - (i % this.w)) <= 1 && this.cells[ni]?.mine) c++ }
          this.cells[i].count = c
        }
      }
    },
    cellClick(idx) {
      const cell = this.cells[idx]
      if (this.won || this.lost) return
      if (cell.revealed) { this.chord(idx); return }
      this.reveal(idx)
    },
    reveal(idx) {
      const cell = this.cells[idx]
      if (cell.flagged) return
      this._startTimer()
      if (this._firstClick) { this._firstClick = false; this._placeMines(idx) }
      cell.revealed = true
      if (cell.mine) { this.lost = true; this.cells.forEach(c => c.revealed = true); if (this._timerInterval) clearInterval(this._timerInterval); this.$emit('ai-event', { type: 'game_lost', difficulty: this.difficulty }); return }
      if (cell.count === 0) this._flood(idx)
      if (this.cells.filter(c => !c.mine && c.revealed).length === this.w * this.h - this.mineCount) {
        this.won = true; this.mineWins++; if (this._timerInterval) clearInterval(this._timerInterval)
        api.post('/settings/', { key: 'minesweeper_wins', value: this.mineWins }).catch(() => {})
        this.$emit('ai-event', { type: 'game_won', difficulty: this.difficulty })
      }
    },
    chord(idx) {
      const cell = this.cells[idx]
      if (!cell.revealed || cell.count === 0 || this.won || this.lost) return
      const w = this.w, total = w * this.h
      let adjFlags = 0
      const dirs = [-1, 1, -w, w, -w-1, -w+1, w-1, w+1]
      const adj = []
      for (const d of dirs) {
        const ni = idx + d
        if (ni >= 0 && ni < total && Math.abs((ni % w) - (idx % w)) <= 1) {
          if (this.cells[ni].flagged) adjFlags++
          else if (!this.cells[ni].revealed) adj.push(ni)
        }
      }
      if (adjFlags !== cell.count) return
      for (const ni of adj) this.reveal(ni)
    },
    _flood(idx) {
      const w = this.w, total = w * this.h
      const dirs8 = [-1, 1, -w, w, -w-1, -w+1, w-1, w+1]
      const isAdj = (a, b) => { const da = Math.abs((a % w) - (b % w)); return da <= 1 && da >= 0 }
      const stack = []
      for (const d of dirs8) { const ni = idx + d; if (ni >= 0 && ni < total && isAdj(ni, idx)) stack.push(ni) }
      while (stack.length) {
        const i = stack.pop()
        const cell = this.cells[i]
        if (!cell || cell.revealed || cell.mine || cell.flagged) continue
        cell.revealed = true
        if (cell.count === 0) {
          for (const d of dirs8) {
            const ni = i + d
            if (ni >= 0 && ni < total && isAdj(ni, i)) stack.push(ni)
          }
        }
      }
    },
    flag(idx) {
      const cell = this.cells[idx]
      if (cell.revealed || this.won || this.lost) return
      cell.flagged = !cell.flagged
      this.flags += cell.flagged ? 1 : -1
    },
    askHelp() {
      this._helped = true; this.newGame(this.difficulty); this.$emit('help', { difficulty: this.difficulty })
    },
    cellClass(c) {
      if (!c.revealed) return c.flagged ? 'ms-flag' : 'ms-hidden'
      if (c.mine) return 'ms-mine'
      return 'ms-num' + c.count
    },
    cellText(c) {
      if (!c.revealed) return c.flagged ? 'P' : ''
      if (c.mine) return 'x'
      return c.count || ''
    }
  }
}
</script>

<style scoped>
.minesweeper { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 8px; }
.ms-header { display: flex; align-items: center; gap: 8px; color: var(--tc); font-size: 13px; }
.ms-counter { min-width: 55px; font-weight: 600; color: #e74c3c; }
.ms-timer { min-width: 40px; font-weight: 600; color: var(--p); }
.ms-face { width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 700; border-radius: 4px; border: 1px solid var(--border); background: var(--sb); color: var(--tc); cursor: pointer; user-select: none; }
.ms-face:hover { background: rgba(255,255,255,.06); }
.ms-diff { padding: 4px; border-radius: 4px; background: var(--bg); color: var(--tc); border: 1px solid var(--border); font-size: 11px; }
.ms-grid { display: grid; gap: 1px; background: var(--border); padding: 1px; border-radius: 4px; }
.ms-grid > div { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; cursor: pointer; user-select: none; border-radius: 2px; transition: background .1s; }
.ms-hidden { background: var(--sb); }
.ms-hidden:hover { background: rgba(255,255,255,.08); }
.ms-hidden:active { background: rgba(255,255,255,.12); }
.ms-flag { background: #c0392b; color: #fff; }
.ms-num0 { background: rgba(255,255,255,.04); color: transparent; }
.ms-num1 { background: rgba(255,255,255,.05); color: #5390d4; }
.ms-num2 { background: rgba(255,255,255,.05); color: #4caf50; }
.ms-num3 { background: rgba(255,255,255,.05); color: #e74c3c; }
.ms-num4 { background: rgba(255,255,255,.05); color: #3498db; }
.ms-num5 { background: rgba(255,255,255,.05); color: #8e44ad; }
.ms-num6 { background: rgba(255,255,255,.05); color: #e67e22; }
.ms-num7 { background: rgba(255,255,255,.05); color: #2c3e50; }
.ms-num8 { background: rgba(255,255,255,.05); color: #7f8c8d; }
.ms-mine { background: #c0392b; color: #fff; }
.ms-msg { font-weight: 600; font-size: 13px; }
.ms-msg.win { color: #4caf50; }
.ms-msg.lose { color: #e74c3c; }
.help-btn { background: var(--p); border: none; color: #fff; border-radius: 6px; padding: 4px 12px; cursor: pointer; font-size: 12px; }
</style>
