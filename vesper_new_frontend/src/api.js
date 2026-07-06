import axios from 'axios'

const api = axios.create({
  baseURL: '',
  timeout: 30000,
})

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('sakura_api_token')
    }
    return Promise.reject(err)
  }
)

api.interceptors.request.use(config => {
  const token = localStorage.getItem('sakura_api_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default api
