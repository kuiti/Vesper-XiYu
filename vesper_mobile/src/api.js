import axios from 'axios'

const api = axios.create({
  baseURL: '',
  timeout: 30000,
})

export function getHost() {
  return localStorage.getItem('vesper_host') || ''
}

export function getWsUrl(path = '/ws/chat') {
  const host = localStorage.getItem('vesper_host') || location.host
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = localStorage.getItem('vesper_api_token') || ''
  let url = `${proto}://${host}${path}`
  if (token) url += `?token=${encodeURIComponent(token)}`
  return url
}

api.interceptors.request.use(config => {
  const host = getHost()
  if (host && !config.url.startsWith('http')) {
    config.url = `http://${host}${config.url}`
  }
  const token = localStorage.getItem('vesper_api_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('vesper_api_token')
    }
    return Promise.reject(err)
  }
)

export default api
