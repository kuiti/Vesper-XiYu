import axios from 'axios'

// 配置版本：config.js 变了就自动清除旧缓存
const CONFIG_VERSION = 'v2';

function _getConfig() {
  const cfg = window.__VESPER_CONFIG__ || {}
  // 版本变化或地址不匹配时，清除旧 localStorage
  const savedVer = localStorage.getItem('vesper_config_ver')
  const savedHost = localStorage.getItem('vesper_server_host')
  if (savedVer !== CONFIG_VERSION || (savedHost && cfg.backendHost && savedHost !== cfg.backendHost)) {
    localStorage.removeItem('vesper_server_host')
    localStorage.removeItem('vesper_server_port')
    localStorage.removeItem('vesper_server_protocol')
    localStorage.removeItem('vesper_api_token')
    localStorage.setItem('vesper_config_ver', CONFIG_VERSION)
  }
  return {
    host: localStorage.getItem('vesper_server_host') || cfg.backendHost || '127.0.0.1',
    port: localStorage.getItem('vesper_server_port') || cfg.backendPort || 8001,
    protocol: localStorage.getItem('vesper_server_protocol') || cfg.backendProtocol || 'http',
    token: localStorage.getItem('vesper_api_token') || cfg.apiToken || '',
  }
}

function getBaseUrl() {
  const c = _getConfig()
  return `${c.protocol}://${c.host}:${c.port}`
}

function getToken() {
  return _getConfig().token
}

// 创建 axios 实例（baseURL 会在拦截器中动态设置）
const api = axios.create({ timeout: 30000 })

// 请求拦截器：动态设置 baseURL 和 Token
api.interceptors.request.use(config => {
  const c = _getConfig()
  config.baseURL = `${c.protocol}://${c.host}:${c.port}`
  if (c.token) {
    config.headers.Authorization = `Bearer ${c.token}`
  }
  return config
})

// 上传类接口使用更长超时
const originalPost = api.post
api.post = function (url, data, config = {}) {
  if (typeof url === 'string' && /upload|import|rebuild|tts/i.test(url)) {
    config.timeout = config.timeout || 120000
  }
  return originalPost.call(this, url, data, config)
}

// WebSocket 连接（每次实时读取 localStorage）
function createWebSocket(path) {
  const c = _getConfig()
  const wsProto = c.protocol === 'https' ? 'wss' : 'ws'
  const base = `${wsProto}://${c.host}:${c.port}`
  const sep = path.includes('?') ? '&' : '?'
  const url = c.token ? `${base}${path}${sep}token=${encodeURIComponent(c.token)}` : `${base}${path}`
  return new WebSocket(url)
}

// 兼容导出
const BASE_URL = getBaseUrl()
const WS_URL = ''

export { api, BASE_URL, WS_URL, createWebSocket, getToken, getBaseUrl }
export default api
