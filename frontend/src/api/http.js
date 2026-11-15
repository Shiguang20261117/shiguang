import axios from 'axios'

import { useAuthStore } from '@/stores/auth'

const http = axios.create({
  baseURL: '/',
  timeout: 15000,
})

// 请求拦截器：自动携带 Bearer token
http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// 响应拦截器：401 视为登录失效，清理凭证并回到登录页
http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const auth = useAuthStore()
      const isLoginRequest = String(error.config?.url || '').includes('/api/auth/login')
      auth.clearAuth()

      if (!isLoginRequest && !window.location.pathname.startsWith('/login')) {
        // 这里用整页跳转而不是 router.push，避免 http.js 与 router 互相引用
        const redirect = encodeURIComponent(window.location.pathname)
        window.location.replace(`/login?redirect=${redirect}`)
      }
    }
    return Promise.reject(error)
  },
)

export default http
