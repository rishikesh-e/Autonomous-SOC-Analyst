import React, { useCallback } from 'react';
import { Ban, Clock, Trash2, RefreshCw, AlertCircle, Shield } from 'lucide-react';
import { usePolling } from '../hooks/usePolling';
import {
  getBlockedIPs,
  getRateLimitedIPs,
  getAlerts,
  unblockIP,
} from '../utils/api';
import type { BlockedIP } from '../types';
import { cn, formatDate, formatRelativeTime } from '../utils/helpers';

export function Actions() {
  const { data: blockedData, refetch: refetchBlocked } = usePolling<{
    blocked_ips: BlockedIP[];
    count: number;
  }>({
    fetcher: getBlockedIPs,
    interval: 10000,
  });

  const { data: rateLimitedData, refetch: refetchRateLimited } = usePolling<{
    rate_limited: BlockedIP[];
    count: number;
  }>({
    fetcher: getRateLimitedIPs,
    interval: 10000,
  });

  const { data: alertsData, refetch: refetchAlerts } = usePolling<{
    alerts: Array<{
      target: string;
      sent_at: string;
      priority: string;
      message: string;
    }>;
  }>({
    fetcher: () => getAlerts(20),
    interval: 10000,
  });

  const handleUnblock = useCallback(async (ip: string) => {
    try {
      await unblockIP(ip);
      refetchBlocked();
    } catch (error) {
      console.error('Failed to unblock IP:', error);
    }
  }, [refetchBlocked]);

  const handleRefresh = useCallback(async () => {
    await Promise.all([refetchBlocked(), refetchRateLimited(), refetchAlerts()]);
  }, [refetchBlocked, refetchRateLimited, refetchAlerts]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Defensive Actions</h1>
          <p className="text-soc-text-muted mt-1">
            View and manage automated defensive responses
          </p>
        </div>
        <button
          onClick={handleRefresh}
          className="flex items-center space-x-2 px-4 py-2 bg-soc-accent rounded-lg font-medium hover:bg-blue-600 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-soc-card rounded-xl border border-red-500/20 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-soc-text-muted">Blocked IPs</p>
              <p className="text-3xl font-bold text-red-400 mt-1">
                {blockedData?.count || 0}
              </p>
            </div>
            <Ban className="w-8 h-8 text-red-400" />
          </div>
        </div>
        <div className="bg-soc-card rounded-xl border border-amber-600/20 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-soc-text-muted">Rate Limited</p>
              <p className="text-3xl font-bold text-amber-400 mt-1">
                {rateLimitedData?.count || 0}
              </p>
            </div>
            <Clock className="w-8 h-8 text-amber-400" />
          </div>
        </div>
        <div className="bg-soc-card rounded-xl border border-blue-500/20 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-soc-text-muted">Alerts Sent</p>
              <p className="text-3xl font-bold text-blue-400 mt-1">
                {alertsData?.alerts?.length || 0}
              </p>
            </div>
            <AlertCircle className="w-8 h-8 text-blue-400" />
          </div>
        </div>
      </div>

      {/* Blocked IPs */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center space-x-2">
            <Ban className="w-5 h-5 text-red-400" />
            <span>Blocked IPs</span>
          </h3>
        </div>

        {blockedData?.blocked_ips && blockedData.blocked_ips.length > 0 ? (
          <div className="space-y-3">
            {blockedData.blocked_ips.map((item) => (
              <div
                key={item.ip}
                className="flex items-center justify-between p-4 bg-soc-dark/50 rounded-lg"
              >
                <div className="flex items-center space-x-4">
                  <div className="p-2 bg-red-500/20 rounded-lg">
                    <Shield className="w-5 h-5 text-red-400" />
                  </div>
                  <div>
                    <p className="font-mono font-medium">{item.ip}</p>
                    <p className="text-sm text-soc-text-muted">{item.reason}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="text-right">
                    <p className="text-sm text-soc-text-muted">
                      {item.permanent ? 'Permanent' : `${item.duration_hours}h`}
                    </p>
                    <p className="text-xs text-soc-text-muted">
                      {formatRelativeTime(item.blocked_at)}
                    </p>
                  </div>
                  <button
                    onClick={() => handleUnblock(item.ip)}
                    className="p-2 hover:bg-red-500/20 rounded-lg transition-colors"
                    title="Unblock IP"
                  >
                    <Trash2 className="w-4 h-4 text-red-400" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-soc-text-muted">
            <Ban className="w-8 h-8 mx-auto mb-2" />
            <p>No blocked IPs</p>
          </div>
        )}
      </div>

      {/* Rate Limited IPs */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center space-x-2">
            <Clock className="w-5 h-5 text-amber-400" />
            <span>Rate Limited IPs</span>
          </h3>
        </div>

        {rateLimitedData?.rate_limited && rateLimitedData.rate_limited.length > 0 ? (
          <div className="space-y-3">
            {rateLimitedData.rate_limited.map((item) => (
              <div
                key={item.ip}
                className="flex items-center justify-between p-4 bg-soc-dark/50 rounded-lg"
              >
                <div className="flex items-center space-x-4">
                  <div className="p-2 bg-amber-600/20 rounded-lg">
                    <Clock className="w-5 h-5 text-amber-400" />
                  </div>
                  <div>
                    <p className="font-mono font-medium">{item.ip}</p>
                    <p className="text-sm text-soc-text-muted">{item.reason}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-soc-text-muted">
                    {item.duration_hours} req/min
                  </p>
                  <p className="text-xs text-soc-text-muted">
                    {formatRelativeTime(item.blocked_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-soc-text-muted">
            <Clock className="w-8 h-8 mx-auto mb-2" />
            <p>No rate limited IPs</p>
          </div>
        )}
      </div>

      {/* Recent Alerts */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 text-blue-400" />
            <span>Recent Alerts</span>
          </h3>
        </div>

        {alertsData?.alerts && alertsData.alerts.length > 0 ? (
          <div className="space-y-3">
            {alertsData.alerts.map((alert, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-4 bg-soc-dark/50 rounded-lg"
              >
                <div className="flex items-center space-x-4">
                  <div
                    className={cn(
                      'p-2 rounded-lg',
                      alert.priority === 'high' || alert.priority === 'critical'
                        ? 'bg-red-500/20'
                        : 'bg-blue-500/20'
                    )}
                  >
                    <AlertCircle
                      className={cn(
                        'w-5 h-5',
                        alert.priority === 'high' || alert.priority === 'critical'
                          ? 'text-red-400'
                          : 'text-blue-400'
                      )}
                    />
                  </div>
                  <div>
                    <p className="font-medium">{alert.target}</p>
                    <p className="text-sm text-soc-text-muted">{alert.message}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span
                    className={cn(
                      'px-2 py-1 rounded text-xs font-medium',
                      alert.priority === 'critical'
                        ? 'bg-red-500/20 text-red-400'
                        : alert.priority === 'high'
                          ? 'bg-orange-500/20 text-orange-400'
                          : 'bg-blue-500/20 text-blue-400'
                    )}
                  >
                    {alert.priority}
                  </span>
                  <p className="text-xs text-soc-text-muted mt-1">
                    {formatRelativeTime(alert.sent_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-soc-text-muted">
            <AlertCircle className="w-8 h-8 mx-auto mb-2" />
            <p>No alerts sent</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default Actions;
