import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Proxy /api → backend:8002 so the frontend and backend share the same origin
// from the browser's perspective (no CORS hassles in dev).
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3003,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
    },
  },
});

