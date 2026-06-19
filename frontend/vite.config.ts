import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 개발 중 /api 요청을 FastAPI 백엔드로 프록시
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
