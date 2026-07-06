import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5174,
    proxy: {
      '/settings': 'http://127.0.0.1:8060',
      '/chat': 'http://127.0.0.1:8060',
      '/characters': 'http://127.0.0.1:8060',
      '/memory': 'http://127.0.0.1:8060',
      '/episodes': 'http://127.0.0.1:8060',
      '/shared-moments': 'http://127.0.0.1:8060',
      '/favorites': 'http://127.0.0.1:8060',
      '/avatar': 'http://127.0.0.1:8060',
      '/avatars': 'http://127.0.0.1:8060',
      '/relationship': 'http://127.0.0.1:8060',
      '/emotion': 'http://127.0.0.1:8060',
      '/tts': 'http://127.0.0.1:8060',
      '/ws': { target: 'ws://127.0.0.1:8060', ws: true },
    },
  },
})
