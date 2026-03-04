import { useEffect, useRef, useState, useCallback } from 'react';
import type { DashboardMetrics, AgentLog, SystemStatus } from '../types';
import { getDashboardMetrics, getAgentLogs, getSystemStatus } from '../utils/api';

interface DashboardData {
  metrics: DashboardMetrics | null;
  logs: AgentLog[];
  status: SystemStatus | null;
}

interface UseDashboardWebSocketReturn {
  data: DashboardData;
  isConnected: boolean;
  connectionMode: 'websocket' | 'polling' | 'disconnected';
  error: string | null;
  reconnect: () => void;
  refetch: () => void;
}

// Token storage key
const TOKEN_KEY = 'soc_auth_token';

// WebSocket URL - uses current host for both dev (Vite proxy) and production
const getWebSocketUrl = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = localStorage.getItem(TOKEN_KEY);
  const baseUrl = `${protocol}//${window.location.host}/api/ws/dashboard`;
  // Add token as query parameter for WebSocket authentication
  return token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;
};

export function useDashboardWebSocket(): UseDashboardWebSocketReturn {
  const [data, setData] = useState<DashboardData>({
    metrics: null,
    logs: [],
    status: null,
  });
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useFallback, setUseFallback] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const maxReconnectAttempts = 3; // Reduced - fallback to polling faster
  const reconnectInterval = 2000;

  // Fallback polling function
  const fetchDataViaPolling = useCallback(async () => {
    try {
      const [metrics, logsData, status] = await Promise.all([
        getDashboardMetrics(),
        getAgentLogs(undefined, 20),
        getSystemStatus(),
      ]);
      setData({
        metrics,
        logs: logsData.logs,
        status,
      });
      setError(null);
    } catch (err) {
      console.error('[Polling] Failed to fetch data:', err);
    }
  }, []);

  // Start polling fallback
  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current) return;

    console.log('[Fallback] Starting polling mode');
    setUseFallback(true);

    // Initial fetch
    fetchDataViaPolling();

    // Start interval
    pollingIntervalRef.current = setInterval(fetchDataViaPolling, 5000);
  }, [fetchDataViaPolling]);

  // Stop polling
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setUseFallback(false);
  }, []);

  const connect = useCallback(() => {
    // Don't create new connection if one is already open or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    // Don't try WebSocket if already in fallback mode
    if (useFallback && reconnectAttemptsRef.current >= maxReconnectAttempts) {
      return;
    }

    // Close any existing connection before creating new one
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    try {
      const ws = new WebSocket(getWebSocketUrl());

      ws.onopen = () => {
        console.log('[WebSocket] Connected to dashboard');
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
        stopPolling(); // Stop polling when WebSocket connects

        // Request initial data with error handling
        try {
          ws.send(JSON.stringify({ type: 'subscribe', channels: ['metrics', 'logs', 'status'] }));
        } catch (err) {
          console.debug('[WebSocket] Failed to send subscription:', err);
        }
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          switch (message.type) {
            case 'metrics':
              setData(prev => ({ ...prev, metrics: message.data }));
              break;
            case 'logs':
              setData(prev => ({ ...prev, logs: message.data.logs || message.data }));
              break;
            case 'status':
              setData(prev => ({ ...prev, status: message.data }));
              break;
            case 'full_update':
              setData({
                metrics: message.data.metrics,
                logs: message.data.logs?.logs || message.data.logs || [],
                status: message.data.status,
              });
              break;
            case 'incident_update':
              // Refresh metrics when incident changes
              try {
                ws.send(JSON.stringify({ type: 'refresh', channel: 'metrics' }));
              } catch (err) {
                console.debug('[WebSocket] Failed to request metrics refresh:', err);
              }
              break;
            default:
              console.log('[WebSocket] Unknown message type:', message.type);
          }
        } catch (err) {
          console.error('[WebSocket] Failed to parse message:', err);
        }
      };

      ws.onerror = (event) => {
        // Connection errors are common (server restart, network issues) - don't treat as fatal
        console.log('[WebSocket] Connection error - will attempt reconnect');
      };

      ws.onclose = (event) => {
        // Clean close (1000) or going away (1001) are normal
        // Abnormal closures (1006) happen on connection reset/server restart
        // Auth error (4001) means token is invalid
        const isAbnormal = event.code === 1006;
        const isAuthError = event.code === 4001;

        if (isAuthError) {
          console.log('[WebSocket] Authentication failed:', event.reason);
          setError('Authentication failed. Please log in again.');
          // Don't reconnect on auth errors
          setIsConnected(false);
          wsRef.current = null;
          return;
        } else if (isAbnormal) {
          console.log('[WebSocket] Connection reset (server may have restarted)');
        } else {
          console.log('[WebSocket] Disconnected:', event.code, event.reason);
        }
        setIsConnected(false);

        // Clear the ref since this connection is done
        wsRef.current = null;

        // Attempt reconnection or fallback to polling
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++;
          // Use longer delay for abnormal closures (server might be restarting)
          const baseDelay = isAbnormal ? 3000 : reconnectInterval;
          const delay = baseDelay * reconnectAttemptsRef.current;
          console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else {
          console.log('[WebSocket] Max attempts reached, falling back to polling');
          startPolling();
        }
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('[WebSocket] Connection error:', err);
      // Fallback to polling on error
      if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
        startPolling();
      }
    }
  }, [useFallback, stopPolling, startPolling]);

  const reconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
    }
    stopPolling();
    reconnectAttemptsRef.current = 0;
    setError(null);
    connect();
  }, [connect, stopPolling]);

  const refetch = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'refresh', channel: 'all' }));
      } catch (err) {
        // Connection may have closed between readyState check and send
        console.debug('[WebSocket] Failed to send refresh request:', err);
        // Fallback to polling if WebSocket send fails
        fetchDataViaPolling();
      }
    } else if (useFallback) {
      fetchDataViaPolling();
    }
  }, [useFallback, fetchDataViaPolling]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        // Remove event handlers to prevent callbacks after unmount
        wsRef.current.onopen = null;
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      stopPolling();
    };
  }, [connect, stopPolling]);

  // Determine connection mode
  const connectionMode = isConnected ? 'websocket' : useFallback ? 'polling' : 'disconnected';

  return {
    data,
    isConnected: isConnected || useFallback,
    connectionMode,
    error,
    reconnect,
    refetch
  };
}

export default useDashboardWebSocket;
