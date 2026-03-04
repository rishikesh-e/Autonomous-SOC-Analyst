import React from 'react';
import { Bot, RefreshCw } from 'lucide-react';
import { AgentLogsPanel } from '../components/AgentLogsPanel';
import { usePolling } from '../hooks/usePolling';
import { getAgentLogs } from '../utils/api';
import type { AgentLog } from '../types';

export function AgentLogs() {
  const { data, refetch, loading } = usePolling<{ logs: AgentLog[] }>({
    fetcher: () => getAgentLogs(undefined, 100),
    interval: 10000,
  });

  // Group logs by agent
  const logsByAgent = React.useMemo(() => {
    if (!data?.logs) return {};
    return data.logs.reduce(
      (acc, log) => {
        const agent = log.agent;
        if (!acc[agent]) acc[agent] = [];
        acc[agent].push(log);
        return acc;
      },
      {} as Record<string, AgentLog[]>
    );
  }, [data]);

  const agentStats = React.useMemo(() => {
    if (!data?.logs) return [];
    const stats: Record<string, { total: number; success: number; avgDuration: number }> = {};

    data.logs.forEach((log) => {
      if (!stats[log.agent]) {
        stats[log.agent] = { total: 0, success: 0, avgDuration: 0 };
      }
      stats[log.agent].total++;
      if (log.result === 'success') stats[log.agent].success++;
      if (log.duration_ms) {
        stats[log.agent].avgDuration =
          (stats[log.agent].avgDuration * (stats[log.agent].total - 1) + log.duration_ms) /
          stats[log.agent].total;
      }
    });

    return Object.entries(stats).map(([agent, stat]) => ({
      agent,
      ...stat,
      successRate: stat.total > 0 ? (stat.success / stat.total) * 100 : 0,
    }));
  }, [data]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agent Logs</h1>
          <p className="text-soc-text-muted mt-1">
            View decision logs from all SOC agents
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 bg-soc-accent rounded-lg font-medium hover:bg-blue-600 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Agent Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {agentStats.map((stat) => (
          <div
            key={stat.agent}
            className="bg-soc-card rounded-xl border border-soc-border p-4"
          >
            <div className="flex items-center space-x-3 mb-3">
              <Bot className="w-5 h-5 text-soc-accent" />
              <span className="font-medium text-sm">{stat.agent}</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <p className="text-xl font-bold">{stat.total}</p>
                <p className="text-xs text-soc-text-muted">Calls</p>
              </div>
              <div>
                <p className="text-xl font-bold text-emerald-400">
                  {stat.successRate.toFixed(0)}%
                </p>
                <p className="text-xs text-soc-text-muted">Success</p>
              </div>
              <div>
                <p className="text-xl font-bold text-blue-400">
                  {stat.avgDuration.toFixed(0)}
                </p>
                <p className="text-xs text-soc-text-muted">Avg ms</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Logs by Agent */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {Object.entries(logsByAgent).map(([agent, logs]) => (
          <AgentLogsPanel
            key={agent}
            title={agent}
            logs={logs}
            maxHeight="400px"
          />
        ))}
      </div>

      {/* All Logs */}
      <AgentLogsPanel
        title="All Agent Logs"
        logs={data?.logs || []}
        maxHeight="600px"
      />
    </div>
  );
}

export default AgentLogs;
