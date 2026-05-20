import axios from 'axios'

const port = (window.__VESPER_CONFIG__ && window.__VESPER_CONFIG__.backendPort) || 8001
const BASE_URL = `http://127.0.0.1:${port}`
const WS_URL = `ws://127.0.0.1:${port}`

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
})

export { api, BASE_URL, WS_URL }
export default api
