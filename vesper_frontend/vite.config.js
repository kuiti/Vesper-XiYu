import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/ws': { target: 'http://127.0.0.1:8001', ws: true },
      '/api': { target: 'http://127.0.0.1:8001' },
      '/auth': { target: 'http://127.0.0.1:8001' },
      '/avatar': { target: 'http://127.0.0.1:8001' },
      '/avatars': { target: 'http://127.0.0.1:8001' },
      '/characters': { target: 'http://127.0.0.1:8001' },
      '/chat': { target: 'http://127.0.0.1:8001' },
      '/emotion': { target: 'http://127.0.0.1:8001' },
      '/settings': { target: 'http://127.0.0.1:8001' },
      '/tts': { target: 'http://127.0.0.1:8001' },
      '/memory': { target: 'http://127.0.0.1:8001' },
      '/export': { target: 'http://127.0.0.1:8001' },
      '/rag': { target: 'http://127.0.0.1:8001' },
    }
  }
})
