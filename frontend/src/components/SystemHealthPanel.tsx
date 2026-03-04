import React from 'react';
import {
  Activity,
  Database,
  Brain,
  Zap,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
} from 'lucide-react';
import type { SystemStatus, DashboardMetrics } from '../types';
import { cn } from '../utils/helpers';

interface SystemHealthPanelProps {
  status: SystemStatus | null;
  metrics: DashboardMetrics | null;
  title?: string;
}

interface HealthIndicator {
  label: string;
  value: string;
  status: 'healthy' | 'warning' | 'error' | 'unknown';
  icon: React.ElementType;
  metric?: string;
}

export function SystemHealthPanel({
  status,
  metrics,
  title = 'System Health',
}: SystemHealthPanelProps) {
  const healthIndicators: HealthIndicator[] = React.useMemo(() => {
    const indicators: HealthIndicator[] = [
      {
        label: 'Elasticsearch',
        value: status?.elasticsearch === 'connected' ? 'Connected' : 'Disconnected',
        status: status?.elasticsearch === 'connected' ? 'healthy' : 'error',
        icon: Database,
        metric: metrics?.logs_ingested_24h
          ? `${(metrics.logs_ingested_24h / 1000).toFixed(1)}K logs/24h`
          : undefined,
      },
      {
        label: 'ML Detector',
        value: status?.anomaly_detector === 'ready' ? 'Ready' : 'Not Ready',
        status: status?.anomaly_detector === 'ready' ? 'healthy' : 'warning',
        icon: Brain,
        metric: metrics?.anomalies_detected
          ? `${metrics.anomalies_detected} anomalies`
          : undefined,
      },
      {
        label: 'Detection Service',
        value: status?.detection_running ? 'Running' : 'Stopped',
        status: status?.detection_running ? 'healthy' : 'warning',
        icon: Activity,
        metric: status?.detection_running ? 'Active monitoring' : 'Paused',
      },
      {
        label: 'LLM API',
        value: status?.groq_api === 'configured' ? 'Configured' : 'Not Set',
        status: status?.groq_api === 'configured' ? 'healthy' : 'error',
        icon: Zap,
        metric: 'Groq API',
      },
    ];
    return indicators;
  }, [status, metrics]);

  const overallHealth = React.useMemo(() => {
    const errorCount = healthIndicators.filter((i) => i.status === 'error').length;
    const warningCount = healthIndicators.filter((i) => i.status === 'warning').length;
    if (errorCount > 0) return 'error';
    if (warningCount > 0) return 'warning';
    return 'healthy';
  }, [healthIndicators]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-emerald-500" />;
      case 'warning':
        return <AlertCircle className="w-4 h-4 text-amber-500" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'bg-emerald-500/10 border-emerald-500/30';
      case 'warning':
        return 'bg-amber-500/10 border-amber-500/30';
      case 'error':
        return 'bg-red-500/10 border-red-500/30';
      default:
        return 'bg-gray-500/10 border-gray-500/30';
    }
  };

  return (
    <div className="bg-soc-card rounded-xl border border-soc-border p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <div
          className={cn(
            'px-3 py-1 rounded-full text-xs font-medium flex items-center gap-1.5',
            overallHealth === 'healthy' && 'bg-emerald-500/20 text-emerald-400',
            overallHealth === 'warning' && 'bg-amber-500/20 text-amber-400',
            overallHealth === 'error' && 'bg-red-500/20 text-red-400'
          )}
        >
          {getStatusIcon(overallHealth)}
          <span className="capitalize">{overallHealth}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {healthIndicators.map((indicator) => (
          <div
            key={indicator.label}
            className={cn(
              'p-4 rounded-lg border transition-colors',
              getStatusColor(indicator.status)
            )}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <indicator.icon className="w-4 h-4 text-soc-text-muted" />
                <span className="text-sm font-medium text-white">
                  {indicator.label}
                </span>
              </div>
              {getStatusIcon(indicator.status)}
            </div>
            <div className="mt-2">
              <p
                className={cn(
                  'text-sm font-semibold',
                  indicator.status === 'healthy' && 'text-emerald-400',
                  indicator.status === 'warning' && 'text-amber-400',
                  indicator.status === 'error' && 'text-red-400',
                  indicator.status === 'unknown' && 'text-gray-400'
                )}
              >
                {indicator.value}
              </p>
              {indicator.metric && (
                <p className="text-xs text-soc-text-muted mt-1">{indicator.metric}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Quick Stats */}
      {metrics && (
        <div className="mt-4 pt-4 border-t border-soc-border">
          <div className="grid grid-cols-4 gap-2 text-center">
            <div>
              <p className="text-xl font-bold text-white">
                {metrics.total_incidents || 0}
              </p>
              <p className="text-xs text-soc-text-muted">Incidents</p>
            </div>
            <div>
              <p className="text-xl font-bold text-amber-400">
                {metrics.pending_approval || 0}
              </p>
              <p className="text-xs text-soc-text-muted">Pending</p>
            </div>
            <div>
              <p className="text-xl font-bold text-red-400">
                {metrics.critical_incidents || 0}
              </p>
              <p className="text-xs text-soc-text-muted">Critical</p>
            </div>
            <div>
              <p className="text-xl font-bold text-emerald-400">
                {metrics.blocked_ips || 0}
              </p>
              <p className="text-xs text-soc-text-muted">Blocked</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SystemHealthPanel;
