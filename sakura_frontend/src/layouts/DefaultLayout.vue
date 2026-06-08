// layouts/DefaultLayout.vue — 三栏布局骨架
// 左导航 + 内容区（右面板保留扩展）
<template>
  <n-layout position="absolute" style="height:100vh">
    <n-layout has-sider style="height:100vh">
      <!-- 左边栏：导航 -->
      <n-layout-sider
        :width="56"
        :collapsed-width="56"
        show-trigger="bar"
        collapse-mode="width"
        :collapsed="true"
        :native-scrollbar="false"
        bordered
        style="background:var(--sb,#161927);display:flex;flex-direction:column;align-items:center;padding-top:12px;border-right:1px solid var(--border,#252d3a)"
      >
        <n-menu
          :value="activeKey"
          :collapsed="true"
          :collapsed-width="56"
          :indent="0"
          @update:value="onNav"
          :options="navItems"
          style="flex:1"
        />
      </n-layout-sider>

      <!-- 主内容区 -->
      <n-layout-content :native-scrollbar="false" style="background:var(--cb,#0f1119)">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup>
import { computed, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NLayout, NLayoutSider, NLayoutContent, NMenu, NIcon } from 'naive-ui'
import { ChatboxEllipses, Apps, Book, StatsChart, GameController, Settings, TimeOutline } from '@vicons/ionicons5'

const route = useRoute()
const router = useRouter()

const activeKey = computed(() => route.name || 'chat')

const navItems = [
  { key: 'chat', icon: () => h(NIcon, null, { default: () => h(ChatboxEllipses) }), label: '聊天' },
  { key: 'tools', icon: () => h(NIcon, null, { default: () => h(Apps) }), label: '工具' },
  { key: 'memory', icon: () => h(NIcon, null, { default: () => h(Book) }), label: '记忆' },
  { key: 'diary', icon: () => h(NIcon, null, { default: () => h(TimeOutline) }), label: '日记' },
  { key: 'stats', icon: () => h(NIcon, null, { default: () => h(StatsChart) }), label: '统计' },
  { key: 'games', icon: () => h(NIcon, null, { default: () => h(GameController) }), label: '游戏' },
  { key: 'settings', icon: () => h(NIcon, null, { default: () => h(Settings) }), label: '设置' },
]

function onNav(key) {
  router.push({ name: key })
}
</script>

<style scoped>
:deep(.n-layout-sider) { border-right: 1px solid var(--border, #252d3a); }
:deep(.n-menu-item) { justify-content: center; }
</style>
