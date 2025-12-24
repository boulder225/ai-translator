import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // Allow external connections
    allowedHosts: [
      '.ngrok.io',
      '.ngrok.app',
      '.ngrok-free.app',
    ],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: (proxy, _options) => {
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            // Forward custom headers
            if (req.headers['x-user-role']) {
              proxyReq.setHeader('X-User-Role', req.headers['x-user-role']);
            }
            if (req.headers['x-username']) {
              proxyReq.setHeader('X-Username', req.headers['x-username']);
            }
          });
        },
      },
    },
  },
})
