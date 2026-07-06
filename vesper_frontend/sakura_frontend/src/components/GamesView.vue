<template>
  <div class="page-view">
    <PageHeader title="游戏" desc="贪吃蛇、扫雷、2048 — AI 会看到你的游戏动态" />
    <div class="page-body">
      <div class="games-grid">
        <div class="game-card"><h3>贪吃蛇</h3><SnakeGame :aiName="aiName" @ai-event="onGameEvent('贪吃蛇', $event)" @help="onHelp('贪吃蛇', $event)" /></div>
        <div class="game-card"><h3>扫雷</h3><Minesweeper :aiName="aiName" @ai-event="onGameEvent('扫雷', $event)" @help="onHelp('扫雷', $event)" /></div>
        <div class="game-card"><h3>2048</h3><Game2048 :aiName="aiName" @ai-event="onGameEvent('2048', $event)" @help="onHelp('2048', $event)" /></div>
      </div>
    </div>
  </div>
</template>

<script>
import PageHeader from './common/PageHeader.vue'
import SnakeGame from './SnakeGame.vue'
import Minesweeper from './Minesweeper.vue'
import Game2048 from './Game2048.vue'

export default {
  components: { PageHeader, SnakeGame, Minesweeper, Game2048 },
  props: { aiName: { type: String, default: '佐仓' } },
  emits: ['game-event', 'ai-help'],
  methods: {
    onGameEvent(game, event) { this.$emit('game-event', { game, ...event, timestamp: new Date().toISOString() }) },
    onHelp(game, event) { this.$emit('ai-help', { game, ...event }) },
  }
}
</script>

<style scoped>
.games-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.game-card { background: var(--surface-card); border: 1px solid var(--border-default); border-radius: 8px; padding: 12px; }
.game-card h3 { font-size: 10px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 8px; }
@media (max-width: 700px) { .games-grid { grid-template-columns: 1fr; gap: 6px; } }
</style>
