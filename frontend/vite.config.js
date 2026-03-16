import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // In dev, proxy /api to the local backend so you
      // don't need CORS or VITE_API_URL for local work
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})