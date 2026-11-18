import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    // GitHub Pages 部署在 https://<user>.github.io/shiguang/ 子路径下；
    // 开发环境仍使用根路径，避免本地访问 5173 端口时必须带 /shiguang/ 前缀
    base: mode === 'production' ? '/shiguang/' : '/',
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      proxy: {
        // 前端统一请求 /api/**，由 Vite 代理到本地后端，规避浏览器跨域限制
        '/api': {
          target: env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
