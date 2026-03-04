import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts';

interface SeverityChartProps {
  data: Record<string, number>;
  title?: string;
}

const COLORS: Record<string, string> = {
  LOW: '#0ea5e9',
  MEDIUM: '#d97706',
  HIGH: '#ea580c',
  CRITICAL: '#dc2626',
};

export function SeverityChart({
  data,
  title = 'Severity Distribution',
}: SeverityChartProps) {
  const chartData = Object.entries(data).map(([name, value]) => ({
    name,
    value,
  }));

  const total = chartData.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className="bg-soc-card rounded-xl border border-soc-border p-6">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
      <div className="h-64">
        {total > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={75}
                paddingAngle={4}
                dataKey="value"
                stroke="#1a1d23"
                strokeWidth={2}
              >
                {chartData.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={COLORS[entry.name] || '#4b5563'}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1a1d23',
                  border: '1px solid #2a2e37',
                  borderRadius: '8px',
                }}
              />
              <Legend
                verticalAlign="bottom"
                height={36}
                formatter={(value) => (
                  <span className="text-soc-text-muted text-sm">{value}</span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-soc-text-muted">
            No data available
          </div>
        )}
      </div>
    </div>
  );
}

export default SeverityChart;
