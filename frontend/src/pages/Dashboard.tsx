import { useState, useCallback } from 'react';
import {
  AlertTriangle,
  Shield,
  Ban,
  Activity,
  RefreshCw,
  Zap,
  Database,
  Brain,
  Key,
  CheckCircle,
  XCircle,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { StatsCard } from '../components/StatsCard';
import { AnomalyChart } from '../components/AnomalyChart';
import { IncidentTable } from '../components/IncidentTable';
import { RiskyIPsList } from '../components/RiskyIPsList';
import { AgentLogsPanel } from '../components/AgentLogsPanel';
import { AttackTypeChart } from '../components/AttackTypeChart';
import { SeverityBarChart } from '../components/SeverityBarChart';
import { IncidentsTimelineChart } from '../components/IncidentsTimelineChart';
import { SecurityInsights } from '../components/SecurityInsights';
import { AutonomyPanel } from '../components/AutonomyPanel';
import { useDashboardWebSocket } from '../hooks/useDashboardWebSocket';
import {
  approveIncident,
  startDetection,
  stopDetection,
} from '../utils/api';
import { cn } from '../utils/helpers';

export function Dashboard() {
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Use WebSocket for real-time updates (with polling fallback)
  const { data, isConnected, connectionMode, refetch, reconnect } = useDashboardWebSocket();
  const { metrics, logs, status } = data;

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    refetch();
    // Give WebSocket time to respond
    setTimeout(() => setIsRefreshing(false), 500);
  }, [refetch]);

  const handleApprove = useCallback(async (id: string) => {
    try {
      await approveIncident(id, true, 'Approved from dashboard');
      refetch();
    } catch (error) {
      console.error('Failed to approve incident:', error);
    }
  }, [refetch]);

  const handleDeny = useCallback(async (id: string) => {
    try {
      await approveIncident(id, false, 'Denied from dashboard');
      refetch();
    } catch (error) {
      console.error('Failed to deny incident:', error);
    }
  }, [refetch]);

  const handleToggleDetection = useCallback(async () => {
    try {
      if (status?.detection_running) {
        await stopDetection();
      } else {
        await startDetection();
      }
      refetch();
    } catch (error) {
      console.error('Failed to toggle detection:', error);
    }
  }, [status, refetch]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Security Dashboard</h1>
          <p className="text-soc-text-muted mt-1">
            Real-time security monitoring and incident management
          </p>
        </div>
        <div className="flex items-center space-x-3">
          {/* Connection Status */}
          <div className={cn(
            'flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium',
            connectionMode === 'websocket'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : connectionMode === 'polling'
              ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
              : 'bg-red-500/10 text-red-400 border border-red-500/20'
          )}>
            {connectionMode === 'websocket' ? (
              <>
                <Wifi className="w-3.5 h-3.5" />
                <span>Live</span>
              </>
            ) : connectionMode === 'polling' ? (
              <>
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Polling</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5" />
                <button onClick={reconnect} className="hover:underline">Reconnect</button>
              </>
            )}
          </div>
          <button
            onClick={handleToggleDetection}
            className={cn(
              'flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-all duration-200',
              status?.detection_running
                ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-600/30 hover:bg-emerald-600/30'
                : 'bg-soc-card text-soc-text-muted border border-soc-border hover:border-soc-text-muted'
            )}
          >
            <Zap className="w-4 h-4" />
            <span>{status?.detection_running ? 'Detection Active' : 'Start Detection'}</span>
          </button>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center space-x-2 px-4 py-2 bg-soc-accent text-white rounded-lg font-medium hover:bg-soc-accent/80 transition-all duration-200 disabled:opacity-50"
          >
            <RefreshCw className={cn('w-4 h-4', isRefreshing && 'animate-spin')} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Enhanced System Health Bar */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            <span className="text-sm font-medium text-white mr-3">System Health</span>
            <div className={cn(
              'px-2 py-0.5 rounded text-xs font-medium',
              status?.elasticsearch === 'connected' && status?.anomaly_detector === 'ready' && status?.groq_api === 'configured'
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'bg-amber-500/20 text-amber-400'
            )}>
              {status?.elasticsearch === 'connected' && status?.anomaly_detector === 'ready' && status?.groq_api === 'configured'
                ? 'All Systems Operational'
                : 'Degraded'}
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-sm">
              <span className="text-soc-text-muted">Pending: </span>
              <span className="text-amber-400 font-semibold">{status?.pending_incidents || 0}</span>
            </div>
            <div className="text-sm">
              <span className="text-soc-text-muted">Critical: </span>
              <span className="text-red-400 font-semibold">{metrics?.severity_distribution?.CRITICAL || 0}</span>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
          <ServiceStatus
            icon={Database}
            name="Elasticsearch"
            status={status?.elasticsearch === 'connected'}
            detail={status?.elasticsearch === 'connected' ? 'Log ingestion active' : 'Connection failed'}
          />
          <ServiceStatus
            icon={Brain}
            name="ML Detector"
            status={status?.anomaly_detector === 'ready'}
            detail={status?.anomaly_detector === 'ready' ? 'Isolation Forest ready' : 'Model not trained'}
          />
          <ServiceStatus
            icon={Activity}
            name="Detection Loop"
            status={status?.detection_running}
            detail={status?.detection_running ? 'Monitoring logs' : 'Paused'}
          />
          <ServiceStatus
            icon={Key}
            name="Groq LLM"
            status={status?.groq_api === 'configured'}
            detail={status?.groq_api === 'configured' ? 'API key configured' : 'API key missing'}
          />
        </div>
      </div>

      {/* Autonomous Mode Panel */}
      <AutonomyPanel />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Incidents"
          value={metrics?.total_incidents || 0}
          icon={AlertTriangle}
          color="red"
        />
        <StatsCard
          title="Pending Approval"
          value={metrics?.pending_approval || 0}
          icon={Shield}
          color="yellow"
        />
        <StatsCard
          title="Blocked IPs"
          value={metrics?.blocked_ips || 0}
          icon={Ban}
          color="purple"
        />
        <StatsCard
          title="Detection Status"
          value={status?.detection_running ? 'Active' : 'Stopped'}
          icon={Activity}
          color={status?.detection_running ? 'green' : 'teal'}
        />
      </div>

      {/* Anomaly Chart - Full Width */}
      <AnomalyChart data={metrics?.time_series_anomalies || []} />

      {/* Charts Row 2 - Attack & Severity Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AttackTypeChart incidents={metrics?.recent_incidents || []} />
        <SeverityBarChart incidents={metrics?.recent_incidents || []} />
      </div>

      {/* Incidents Timeline */}
      <IncidentsTimelineChart incidents={metrics?.recent_incidents || []} />

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Incidents & Insights */}
        <div className="lg:col-span-2 space-y-6">
          {/* Security Insights */}
          <SecurityInsights metrics={metrics} />

          {/* Recent Incidents */}
          <IncidentTable
            incidents={metrics?.recent_incidents || []}
            onApprove={handleApprove}
            onDeny={handleDeny}
            title="Recent Incidents"
          />
        </div>

        {/* Right Sidebar */}
        <div className="space-y-6">
          <RiskyIPsList ips={metrics?.top_risky_ips || []} />
          <AgentLogsPanel logs={logs || []} maxHeight="400px" />
        </div>
      </div>
    </div>
  );
}

function ServiceStatus({
  icon: Icon,
  name,
  status,
  detail,
}: {
  icon: React.ElementType;
  name: string;
  status?: boolean;
  detail: string;
}) {
  return (
    <div className={cn(
      'flex items-center gap-3 p-3 rounded-lg border transition-colors',
      status
        ? 'bg-emerald-500/5 border-emerald-500/20'
        : 'bg-red-500/5 border-red-500/20'
    )}>
      <div className={cn(
        'p-2 rounded-lg',
        status ? 'bg-emerald-500/10' : 'bg-red-500/10'
      )}>
        <Icon className={cn('w-4 h-4', status ? 'text-emerald-400' : 'text-red-400')} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">{name}</span>
          {status ? (
            <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
          ) : (
            <XCircle className="w-3.5 h-3.5 text-red-500" />
          )}
        </div>
        <p className="text-xs text-soc-text-muted truncate">{detail}</p>
      </div>
    </div>
  );
}

export default Dashboard;
