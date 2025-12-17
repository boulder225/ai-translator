import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: (proxy, _options) => {
          // #region agent log
          proxy.on('proxyReq', (proxyReq, req, res) => {
            fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'vite.config.js:proxyReq',message:'Proxy forwarding request',data:{method:req.method,url:req.url,target:'http://127.0.0.1:8000'},timestamp:Date.now(),sessionId:'debug-session',runId:'post-fix',hypothesisId:'A,B,D'})}).catch(()=>{});
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'vite.config.js:proxyRes',message:'Proxy received response',data:{statusCode:proxyRes.statusCode,url:req.url},timestamp:Date.now(),sessionId:'debug-session',runId:'post-fix',hypothesisId:'A,B,D'})}).catch(()=>{});
          });
          proxy.on('error', (err, req, res) => {
            fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'vite.config.js:proxyError',message:'Proxy error occurred',data:{error:err.message,code:err.code,url:req?.url},timestamp:Date.now(),sessionId:'debug-session',runId:'post-fix',hypothesisId:'A,C'})}).catch(()=>{});
          });
          // #endregion
        },
      },
    },
  },
})
