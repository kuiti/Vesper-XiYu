<template>
  <GamesView :aiName="settingsStore.aiName" @game-event="onGameEvent" @ai-help="onAiHelp" />
</template>

<script>
import { useSettingsStore } from '../stores/settings.js'
import { useChatStore } from '../stores/chat.js'
import GamesView from '../components/GamesView.vue'

export default {
  components: { GamesView },
  setup() {
    const settingsStore = useSettingsStore()
    const chatStore = useChatStore()

    function onGameEvent(evt) {
      if (!evt || chatStore.isStreaming) return
      const map = { high_score: '刷新了最高分', game_won: '通关了', game_lost: '输了', reached_2048: '合出了2048', game_over: '游戏结束' }
      const act = map[evt.type] || evt.type
      let msg = evt.game + '：' + act + '！'
      if (evt.score) msg += '得分' + evt.score
      if (evt.difficulty) msg += '，' + ({ easy: '简单', medium: '中等', hard: '困难' }[evt.difficulty] || evt.difficulty)
      sendSystem(msg)
    }

    function onAiHelp(evt) {
      if (!evt) return
      sendSystem(settingsStore.aiName + '救我！我正玩' + evt.game + '呢，快帮帮我！')
    }

    function sendSystem(msg) {
      if (!chatStore.wsReady || chatStore.isStreaming) return
      chatStore.send({
        message: msg,
        history: chatStore.messages
          .filter(m => !m._sentenceFrag && !m._gameEvent && !m._isGreeting && !m.isProactive)
          .slice(-3).map(m => ({ role: m.role, content: m.content })),
        _system: true,
      })
    }

    return { settingsStore, onGameEvent, onAiHelp }
  },
}
</script>
