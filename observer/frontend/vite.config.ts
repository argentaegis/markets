import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '../', ['BACKEND_PORT', 'FRONTEND_PORT'])
  const backendPort = env.BACKEND_PORT || '8000'
  const frontendPort = parseInt(env.FRONTEND_PORT || '5173')

  return {
    plugins: [react()],
    server: {
      port: frontendPort,
      proxy: {
        '/api': `http://localhost:${backendPort}`,
        '/runs': `http://localhost:${backendPort}`,
        '/ws': { target: `ws://localhost:${backendPort}`, ws: true },
      },
    },
  }
})
