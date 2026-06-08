// App.vue v2 — 重构骨架
// 职责：只做全局 Provider 注册，不承载业务逻辑
<template>
  <n-notification-provider>
    <n-dialog-provider>
      <n-message-provider>
        <router-view />
      </n-message-provider>
    </n-dialog-provider>
  </n-notification-provider>
</template>

<script setup>
import { onMounted } from 'vue'
import { useDialog, useMessage } from 'naive-ui'
import { useUiStore } from './stores/ui.js'
import { useSettingsStore } from './stores/settings.js'

const ui = useUiStore()
const settings = useSettingsStore()

onMounted(() => {
  ui.registerDialog(useDialog())
  ui.registerMessage(useMessage())
  settings.load()
})
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; scrollbar-width: thin; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #0f1119; color: #e2e8f0; overflow: hidden; height: 100dvh;
}
#app { height: 100dvh; }
::selection { background: rgba(106, 159, 216, .35); }
</style>
