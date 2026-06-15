import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './themes.css'

const app = createApp(App)
app.use(createPinia())
app.config.errorHandler = (err, vm, info) => {
  console.error('[Vue Error]', err, info)
}
app.mount('#app')