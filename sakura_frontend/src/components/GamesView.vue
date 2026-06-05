<template>
  <div class="games-view">
    <h2>游戏</h2>
    <p class="hint">AI 会看到你的游戏动态——通关了、新高分时，切回聊天她会知道的。</p>
    <div class="games-grid">
      <div class="game-card"><h3>贪吃蛇</h3><SnakeGame :aiName="aiName" @ai-event="onGameEvent('贪吃蛇', $event)" @help="onHelp('贪吃蛇', $event)" /></div>
      <div class="game-card"><h3>扫雷</h3><Minesweeper :aiName="aiName" @ai-event="onGameEvent('扫雷', $event)" @help="onHelp('扫雷', $event)" /></div>
      <div class="game-card"><h3>2048</h3><Game2048 :aiName="aiName" @ai-event="onGameEvent('2048', $event)" @help="onHelp('2048', $event)" /></div>
    </div>
  </div>
</template>

<script>
import SnakeGame from './SnakeGame.vue'
import Minesweeper from './Minesweeper.vue'
import Game2048 from './Game2048.vue'

export default {
  components: { SnakeGame, Minesweeper, Game2048 },
  props: { aiName: { type: String, default: '佐仓' } },
  emits: ['game-event', 'ai-help'],
  methods: {
    onGameEvent(game, event) {
      this.$emit('game-event', { game, ...event, timestamp: new Date().toISOString() })
    },
    onHelp(game, event) {
      this.$emit('ai-help', { game, ...event })
    }
  }
}
</script>

<style scoped>
.games-view { padding: 20px; overflow-y: auto; height: 100%; }
.games-view h2 { font-size: 18px; font-weight: 600; margin-bottom: 4px; color: var(--tc); }
.hint { color: var(--tc2); font-size: 12px; margin-bottom: 16px; }
.games-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.game-card { background: rgba(255,255,255,.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.game-card h3 { font-size: 13px; color: var(--tc2); margin-bottom: 10px; }

/* 移动端适配 */
@media (max-width: 768px) {
  .games-view { padding: 12px; }
  .games-view h2 { font-size: 16px; margin-bottom: 4px; }
  .hint { font-size: 13px; margin-bottom: 12px; }
  .games-grid { grid-template-columns: 1fr; gap: 10px; }
  .game-card { padding: 12px; }
  .game-card h3 { font-size: 14px; margin-bottom: 8px; }
}
</style>
