import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts';
import { Target } from 'lucide-react';
import type { Incident } from '../types';

interface AttackTypeChartProps {
  incidents: Incident[];
  title?: string;
}

const ATTACK_COLORS: Record<string, string> = {
  BRUTE_FORCE: '#dc2626',
  DDOS: '#ea580c',
  RECONNAISSANCE: '#d97706',
  INJECTION: '#7c3aed',
  SUSPICIOUS_IP: '#0891b2',
  AUTH_FAILURE: '#be185d',
  ANOMALOUS_TRAFFIC: '#059669',
  UNKNOWN: '#64748b',
};

const ATTACK_LABELS: Record<string, string> = {
  BRUTE_FORCE: 'Brute Force',
  DDOS: 'DDoS',
  RECONNAISSANCE: 'Recon',
  INJECTION: 'Injection',
  SUSPICIOUS_IP: 'Suspicious IP',
  AUTH_FAILURE: 'Auth Failure',
  ANOMALOUS_TRAFFIC: 'Anomalous',
  UNKNOWN: 'Unknown',
};

const EMPTY_DATA = [
  { name: 'UNKNOWN', value: 1, label: 'No Data' },
];

export function AttackTypeChart({
  incidents,
  title = 'Attack Type Distribution',
}: AttackTypeChartProps) {
  const attackCounts = React.useMemo(() => {
    if (incidents.length === 0) return [];
    const counts: Record<string, number> = {};
    incidents.forEach((incident) => {
      const type = incident.classification?.attack_type || 'UNKNOWN';
      counts[type] = (counts[type] || 0) + 1;
    });
    return Object.entries(counts)
      .map(([name, value]) => ({
        name,
        value,
        label: ATTACK_LABELS[name] || name,
      }))
      .sort((a, b) => b.value - a.value);
  }, [incidents]);

  const isEmpty = attackCounts.length === 0;
  const chartData = isEmpty ? EMPTY_DATA : attackCounts;
  const total = isEmpty ? 1 : attackCounts.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className="bg-soc-card rounded-xl border border-soc-border p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <Target className="w-5 h-5 text-soc-text-muted" />
      </div>
      <div className="h-64 relative">
        {isEmpty && (
          <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
            <span className="text-soc-text-muted text-sm bg-soc-card/80 px-3 py-1 rounded">No data yet</span>
          </div>
        )}
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={75}
              paddingAngle={isEmpty ? 0 : 3}
              dataKey="value"
              stroke="#1a1d23"
              strokeWidth={2}
            >
              {chartData.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={isEmpty ? '#2a2e37' : (ATTACK_COLORS[entry.name] || '#64748b')}
                />
              ))}
            </Pie>
            {!isEmpty && (
              <>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1a1d23',
                    border: '1px solid #2a2e37',
                    borderRadius: '8px',
                  }}
                  formatter={(value: number, name: string) => [
                    `${value} (${((value / total) * 100).toFixed(1)}%)`,
                    ATTACK_LABELS[name] || name,
                  ]}
                />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  formatter={(value) => (
                    <span className="text-soc-text-muted text-xs">
                      {ATTACK_LABELS[value] || value}
                    </span>
                  )}
                />
              </>
            )}
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default AttackTypeChart;
