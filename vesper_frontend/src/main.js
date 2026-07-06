import { createApp } from 'vue'
import './style.css'
import './themes.css'
import App from './App.vue'
import router from './router.js'

// Restore saved theme
try {
  const t = localStorage.getItem('vesper_theme')
  if (t) document.documentElement.setAttribute('data-theme', t)
} catch (_) {}

const app = createApp(App)
app.use(router)
app.mount('#app')
