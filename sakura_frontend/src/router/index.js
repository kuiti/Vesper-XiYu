// router/index.js — 路由配置（逐步添加页面）
import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('../layouts/DefaultLayout.vue'),
    children: [
      { path: '', name: 'chat', component: () => import('../views/ChatView.vue') },
      // 以下页面逐步从旧 App.vue 迁移
      { path: 'settings', name: 'settings', component: () => import('../views/SettingsView.vue') },
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
