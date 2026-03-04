import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { AlertTriangle } from 'lucide-react';
import type { Incident } from '../types';

interface SeverityBarChartProps {
  incidents: Incident[];
  title?: string;
}

const SEVERITY_ORDER = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

const SEVERITY_COLORS: Record<string, string> = {
  LOW: '#0ea5e9',
  MEDIUM: '#d97706',
  HIGH: '#ea580c',
  CRITICAL: '#dc2626',
};

export function SeverityBarChart({
  incidents,
  title = 'Severity Distribution',
}: SeverityBarChartProps) {
  const severityCounts = React.useMemo(() => {
    const counts: Record<string, number> = {
      LOW: 0,
      MEDIUM: 0,
      HIGH: 0,
      CRITICAL: 0,
    };
    incidents.forEach((incident) => {
      const severity = incident.classification?.severity || 'LOW';
      counts[severity] = (counts[severity] || 0) + 1;
    });
    return SEVERITY_ORDER.map((severity) => ({
      name: severity,
      value: counts[severity],
      color: SEVERITY_COLORS[severity],
    }));
  }, [incidents]);

  const total = severityCounts.reduce((sum, item) => sum + item.value, 0);
  const isEmpty = total === 0;

  return (
    <div className="bg-soc-card rounded-xl border border-soc-border p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <AlertTriangle className="w-5 h-5 text-soc-text-muted" />
      </div>
      <div className="h-64 relative">
        {isEmpty && (
          <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
            <span className="text-soc-text-muted text-sm bg-soc-card/80 px-3 py-1 rounded">No data yet</span>
          </div>
        )}
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={severityCounts} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2e37" horizontal={false} />
            <XAxis
              type="number"
              stroke="#4b5563"
              tick={{ fill: '#9ca3af', fontSize: 11 }}
              axisLine={{ stroke: '#2a2e37' }}
              domain={isEmpty ? [0, 10] : undefined}
            />
            <YAxis
              type="category"
              dataKey="name"
              stroke="#4b5563"
              tick={{ fill: '#9ca3af', fontSize: 11 }}
              axisLine={{ stroke: '#2a2e37' }}
              width={70}
            />
            {!isEmpty && (
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1a1d23',
                  border: '1px solid #2a2e37',
                  borderRadius: '8px',
                }}
                formatter={(value: number) => [
                  `${value} incidents (${total > 0 ? ((value / total) * 100).toFixed(1) : 0}%)`,
                  'Count',
                ]}
              />
            )}
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {severityCounts.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={isEmpty ? '#2a2e37' : entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default SeverityBarChart;
