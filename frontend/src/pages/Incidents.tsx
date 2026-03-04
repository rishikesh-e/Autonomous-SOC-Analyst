import { useState, useCallback } from 'react';
import { RefreshCw, Filter, Bot } from 'lucide-react';
import { IncidentTable } from '../components/IncidentTable';
import { usePolling } from '../hooks/usePolling';
import { getIncidents, approveIncident } from '../utils/api';
import type { Incident, IncidentStatus } from '../types';
import { cn } from '../utils/helpers';

const statusFilters: { value: IncidentStatus | 'ALL'; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'PENDING_APPROVAL', label: 'Pending' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'EXECUTED', label: 'Executed' },
  { value: 'DENIED', label: 'Denied' },
  { value: 'RESOLVED', label: 'Resolved' },
];

export function Incidents() {
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | 'ALL'>('ALL');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const { data, refetch } = usePolling<{ incidents: Incident[]; count: number }>({
    fetcher: () =>
      getIncidents(statusFilter === 'ALL' ? undefined : statusFilter, 100),
    interval: 10000,
  });

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await refetch();
    setIsRefreshing(false);
  }, [refetch]);

  const handleApprove = useCallback(async (id: string) => {
    try {
      await approveIncident(id, true, 'Approved from incidents page');
      refetch();
    } catch (error) {
      console.error('Failed to approve incident:', error);
    }
  }, [refetch]);

  const handleDeny = useCallback(async (id: string) => {
    try {
      await approveIncident(id, false, 'Denied from incidents page');
      refetch();
    } catch (error) {
      console.error('Failed to deny incident:', error);
    }
  }, [refetch]);

  const handleFilterChange = useCallback((value: IncidentStatus | 'ALL') => {
    setStatusFilter(value);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Incidents</h1>
          <p className="text-soc-text-muted mt-1">
            Manage and review security incidents
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="flex items-center space-x-2 px-4 py-2 bg-soc-accent text-white rounded-lg font-medium hover:bg-soc-accent/80 transition-all duration-200 disabled:opacity-50"
        >
          <RefreshCw className={cn('w-4 h-4', isRefreshing && 'animate-spin')} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filters */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-4">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 text-soc-text-muted">
            <Filter className="w-4 h-4" />
            <span className="text-sm">Filter by status:</span>
          </div>
          <div className="flex items-center space-x-2">
            {statusFilters.map((filter) => (
              <button
                key={filter.value}
                onClick={() => handleFilterChange(filter.value)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-sm transition-all duration-200',
                  statusFilter === filter.value
                    ? 'bg-soc-accent/20 text-soc-accent border border-soc-accent/30'
                    : 'bg-soc-dark text-soc-text-muted border border-soc-border hover:border-soc-text-muted/30'
                )}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-4">
        <div className="bg-soc-card rounded-xl border border-soc-border p-4">
          <p className="text-sm text-soc-text-muted">Total</p>
          <p className="text-2xl font-semibold text-white">{data?.count || 0}</p>
        </div>
        <div className="bg-gradient-to-br from-purple-900/30 to-blue-900/30 rounded-xl border border-purple-600/30 p-4">
          <div className="flex items-center space-x-2">
            <Bot className="w-4 h-4 text-purple-400" />
            <p className="text-sm text-soc-text-muted">Auto-Executed</p>
          </div>
          <p className="text-2xl font-semibold text-purple-400">
            {data?.incidents.filter((i) =>
              i.status === 'EXECUTED' && (i.classification?.confidence || 0) >= 0.75
            ).length || 0}
          </p>
        </div>
        <div className="bg-soc-card rounded-xl border border-amber-600/30 p-4">
          <p className="text-sm text-soc-text-muted">Pending</p>
          <p className="text-2xl font-semibold text-amber-400">
            {data?.incidents.filter((i) => i.status === 'PENDING_APPROVAL').length || 0}
          </p>
        </div>
        <div className="bg-soc-card rounded-xl border border-emerald-600/30 p-4">
          <p className="text-sm text-soc-text-muted">Executed</p>
          <p className="text-2xl font-semibold text-emerald-400">
            {data?.incidents.filter((i) => i.status === 'EXECUTED').length || 0}
          </p>
        </div>
        <div className="bg-soc-card rounded-xl border border-red-600/30 p-4">
          <p className="text-sm text-soc-text-muted">Critical</p>
          <p className="text-2xl font-semibold text-red-400">
            {data?.incidents.filter((i) => i.classification?.severity === 'CRITICAL').length || 0}
          </p>
        </div>
      </div>

      {/* Incidents Table */}
      <IncidentTable
        incidents={data?.incidents || []}
        onApprove={handleApprove}
        onDeny={handleDeny}
        title="All Incidents"
      />
    </div>
  );
}

export default Incidents;
