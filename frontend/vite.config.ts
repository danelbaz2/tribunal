import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend is FastAPI on :8000 (ARCHITECTURE.md Part 4). Proxying keeps the
// frontend origin-relative, so no base URL has to be configured per machine.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
