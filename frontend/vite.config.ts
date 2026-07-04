import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Use 127.0.0.1 — on Windows, "localhost" often resolves to IPv6 (::1) while uvicorn binds IPv4 only.
  const apiTarget = env.VITE_PROXY_TARGET || env.VITE_API_URL || 'http://127.0.0.1:8000'
  const proxyTarget = apiTarget.replace('://localhost', '://127.0.0.1')

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
