<template>
  <div class="games-page">
    <div class="games-header"><div class="title">小游戏</div></div>
    <div class="games-body">
      <div class="games-grid">
        <div v-for="g in games" :key="g.name" class="game-card" @click="g.action">
          <div class="game-icon"><i :class="g.icon"></i></div>
          <h4>{{ g.name }}</h4>
          <p>{{ g.desc }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  setup() {
    const games = [
      { name: '2048', desc: '经典数字合成', icon: 'ri-grid-line', action: () => {} },
      { name: '扫雷', desc: '经典益智', icon: 'ri-bomb-line', action: () => {} },
      { name: '贪吃蛇', desc: '经典街机', icon: 'ri-loop-left-line', action: () => {} },
    ]
    return { games }
  }
}
</script>

<style scoped>
.games-page { display: flex; flex-direction: column; height: 100%; }
.games-header { padding: 10px 20px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.games-header .title { font-size: 15px; font-weight: 600; }
.games-body { flex: 1; padding: 20px; overflow-y: auto; }
.games-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.game-card { background: var(--bg-card); border-radius: 12px; border: 1px solid var(--border); padding: 24px; text-align: center; cursor: pointer; }
.game-card:hover { border-color: var(--primary); transform: translateY(-2px); }
.game-icon { font-size: 32px; margin-bottom: 8px; color: var(--primary); }
.game-card h4 { font-size: 14px; font-weight: 600; }
.game-card p { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
</style>
