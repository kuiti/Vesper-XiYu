// router/index.js — 路由配置
import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('../layouts/DefaultLayout.vue'),
    children: [
      { path: '', name: 'chat', component: () => import('../views/ChatView.vue') },
      { path: 'tools', name: 'tools', component: () => import('../views/ToolsView.vue') },
      { path: 'memory', name: 'memory', component: () => import('../views/MemoryView.vue') },
      { path: 'diary', name: 'diary', component: () => import('../views/DiaryView.vue') },
      { path: 'stats', name: 'stats', component: () => import('../views/StatsView.vue') },
      { path: 'games', name: 'games', component: () => import('../views/GamesView.vue') },
      { path: 'settings', name: 'settings', component: () => import('../views/SettingsView.vue') },
      { path: 'history', name: 'history', component: () => import('../views/HistoryView.vue') },
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
