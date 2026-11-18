import axios from 'axios'

import { useAuthStore } from '@/stores/auth'

// 开发环境不配置 VITE_API_BASE_URL，留空后由 Vite 代理 /api 到本地后端；
// 生产环境在 .env.production 中配置真实后端地址。
const baseURL = import.meta.env.VITE_API_BASE_URL || '/'

// GitHub Pages 部署在 /shiguang/ 子路径下，整页跳转时需带上该前缀
const appBase = import.meta.env.BASE_URL.replace(/\/$/, '')

const http = axios.create({
  baseURL,
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

      if (!isLoginRequest) {
        const pathname = window.location.pathname
        // 去掉部署子路径前缀，得到应用内路由路径
        const appPath = appBase && pathname.startsWith(`${appBase}/`)
          ? pathname.slice(appBase.length)
          : pathname

        if (appPath !== '/login') {
          // 这里用整页跳转而不是 router.push，避免 http.js 与 router 互相引用
          const redirect = encodeURIComponent(appPath)
          window.location.replace(`${appBase}/login?redirect=${redirect}`)
        }
      }
    }
    return Promise.reject(error)
  },
)

export default http
