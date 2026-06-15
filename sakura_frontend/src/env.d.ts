/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface SakuraConfig {
  backendHost?: string
  backendPort?: string | number
  backendProtocol?: string
  apiToken?: string
}

interface Window {
  __SAKURA_CONFIG__?: SakuraConfig
}