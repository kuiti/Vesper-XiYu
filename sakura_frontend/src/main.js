// main.js — 入口（注册 Naive UI + Router + Pinia）
import { createApp } from 'vue'
import naive from 'naive-ui'
import { createPinia } from 'pinia'
import router from './router/index.js'
import App from './App.vue'

const app = createApp(App)
app.config.errorHandler = (err, vm, info) => {
  console.error('[Vue Error]', err, info)
}
app.use(naive)
app.use(createPinia())
app.use(router)
app.mount('#app')
