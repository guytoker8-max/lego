import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the API runs separately (uvicorn on :8000) and Vite proxies
// to it. In production the API serves the built files itself, so the site
// and the API share one origin and there is nothing to configure.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000', '/health': 'http://127.0.0.1:8000' },
  },
  build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 900 },
});
