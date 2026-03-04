import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Custom logger to suppress noisy proxy errors
const customLogger = {
  info: (msg: string) => {
    if (!msg.includes('ws proxy socket error')) {
      console.log(msg)
    }
  },
  warn: (msg: string) => {
    if (!msg.includes('ws proxy socket error')) {
      console.warn(msg)
    }
  },
  error: (msg: string) => {
    // Suppress EPIPE/ECONNRESET errors from proxy
    if (msg.includes('EPIPE') || msg.includes('ECONNRESET') || msg.includes('ECONNREFUSED')) {
      return // Silently ignore
    }
    console.error(msg)
  },
  warnOnce: (msg: string) => console.warn(msg),
  clearScreen: () => {},
  hasWarned: false,
  hasErrorLogged: () => false,
}

export default defineConfig({
  plugins: [react()],
  customLogger: customLogger as any,
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
        configure: (proxy, _options) => {
          // Suppress proxy error stack traces - these are expected during backend restarts
          proxy.on('error', (err, _req, res) => {
            // Only log a simple message, not the full stack trace
            if (err.message.includes('ECONNRESET') || err.message.includes('EPIPE') || err.message.includes('ECONNREFUSED')) {
              // Silently ignore connection errors - backend is likely restarting
            } else {
              console.log('[Proxy] Error:', err.message);
            }
            // Prevent default error handling
            if (res && !res.headersSent && 'writeHead' in res) {
              try {
                res.writeHead(502, { 'Content-Type': 'text/plain' });
                res.end('Backend unavailable');
              } catch {
                // Response already sent or closed
              }
            }
          });

          // Handle WebSocket proxy errors
          proxy.on('proxyReqWs', (_proxyReq, _req, socket) => {
            socket.on('error', () => {
              // Silently handle WebSocket errors - these are expected
            });
          });

          // Handle WebSocket connection close
          proxy.on('close', () => {
            // Connection closed, this is normal
          });
        },
      }
    }
  }
})
