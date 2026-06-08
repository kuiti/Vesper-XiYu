<template>
  <n-layout position="absolute" style="height:100vh">
    <n-layout has-sider style="height:100vh">
      <!-- 左导航 -->
      <n-layout-sider
        :width="64" :collapsed-width="64" :collapsed="true"
        :native-scrollbar="false" bordered
        :style="{ background: 'var(--bg-deepest)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '6px 0', borderRight: '1px solid var(--border)' }"
      >
        <div v-for="item in navItems" :key="item.key"
          :class="['nav-item', { active: route.name === item.key || (route.name === 'history' && item.key === 'history') }]"
          @click="go(item.key)"
          :style="{ display:'flex', flexDirection:'column', alignItems:'center', gap:'2px', padding:'9px 4px', width:'100%', cursor:'pointer', color: route.name === item.key || (route.name === 'history' && item.key === 'history') ? '#fff' : 'var(--text-muted)', transition:'all .12s', position:'relative', border:'none', background:'none', fontFamily:'inherit' }"
        >
          <span :style="{ fontSize:'24px', lineHeight:'1' }"><n-icon :component="item.icon" /></span>
          <span :style="{ fontSize:'10px', lineHeight:'1', marginTop:'3px' }">{{ item.label }}</span>
        </div>
        <div style="flex:1"></div>
        <div :class="['nav-item', { active: route.name === 'settings' }]"
          @click="router.push({name:'settings'})"
          :style="{ display:'flex', flexDirection:'column', alignItems:'center', gap:'2px', padding:'7px 4px', width:'100%', cursor:'pointer', color: route.name === 'settings' ? '#fff' : 'var(--text-dim)', transition:'all .12s', border:'none', background:'none', fontFamily:'inherit', fontSize:'20px' }"
        >
          <n-icon :component="Settings" :size="20" />
          <span :style="{ fontSize:'10px', marginTop:'3px' }">设置</span>
        </div>
      </n-layout-sider>

      <!-- 内容区 -->
      <n-layout-content :native-scrollbar="false" style="background:var(--bg-elevated)">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup>
import { h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NLayout, NLayoutSider, NLayoutContent, NIcon } from 'naive-ui'
import {
  ChatboxEllipses, Apps, Book, StatsChart, GameController,
  Bulb, Settings
} from '@vicons/ionicons5'

const route = useRoute()
const router = useRouter()

const navItems = [
  { key: 'chat', icon: ChatboxEllipses, label: '聊天' },
  { key: 'diary', icon: Book, label: '日记' },
  { key: 'tools', icon: Apps, label: '工具' },
  { key: 'stats', icon: StatsChart, label: '统计' },
  { key: 'memory', icon: Bulb, label: '记忆' },
  { key: 'games', icon: GameController, label: '游戏' },
]

function go(key) {
  if (key === 'scroll') {
    window.dispatchEvent(new CustomEvent('scroll-chat'))
    return
  }
  router.push({ name: key })
}
</script>

<style scoped>
.nav-item:hover { color: var(--text) !important; background: var(--bg-elevated); border-radius: 6px; }
.nav-item.active::before {
  content: ''; position: absolute; left: 0; top: 50%;
  transform: translateY(-50%); width: 3px; height: 22px;
  border-radius: 0 3px 3px 0; background: #fff;
}
:deep(.n-layout-sider) { border-right: 1px solid var(--border); }
</style>
