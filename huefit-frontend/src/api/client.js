import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api',
  headers: { Accept: 'application/json' },
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('huefit_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  // Let the browser set multipart boundary. Never force JSON on FormData.
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    if (config.headers && typeof config.headers.delete === 'function') {
      config.headers.delete('Content-Type')
    } else if (config.headers) {
      delete config.headers['Content-Type']
      delete config.headers['content-type']
    }
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('huefit_token')
      localStorage.removeItem('huefit_user')
    }
    return Promise.reject(error)
  },
)

export default api
