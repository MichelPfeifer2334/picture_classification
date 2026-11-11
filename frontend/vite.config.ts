import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // Alle /api-Aufrufe gehen an das FastAPI-Backend → kein CORS im Dev-Betrieb
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
