import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // 兼容两个变量名：.env.example 定义的是 VITE_API_BASE_URL，
  // 历史配置用过 VITE_BACKEND_URL，避免配置名漂移导致代理悄悄落到默认端口
  const backendUrl =
    env.VITE_API_BASE_URL || env.VITE_BACKEND_URL || 'http://localhost:8000'

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      }
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true
        }
      }
    },
    build: {
      rollupOptions: {
        output: {
          // 大依赖单独分包：更新业务代码时这些库走浏览器缓存
          manualChunks: {
            'vendor-vue': ['vue', 'vue-router'],
            'vendor-antd': ['ant-design-vue'],
            'vendor-echarts': ['echarts', 'vue-echarts'],
            'vendor-export': ['jspdf', 'html2canvas'],
          },
        },
      },
    }
  }
})

