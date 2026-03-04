import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import type { TimeSeriesPoint } from '../types';
import { format } from 'date-fns';

interface AnomalyChartProps {
  data: TimeSeriesPoint[];
  title?: string;
}

// Empty data shows last 2 hours in 10-minute intervals (12 points)
const EMPTY_DATA = Array.from({ length: 12 }, (_, i) => {
  const now = new Date();
  const minutesAgo = (11 - i) * 10;
  const time = new Date(now.getTime() - minutesAgo * 60000);
  return {
    time: `${String(time.getHours()).padStart(2, '0')}:${String(Math.floor(time.getMinutes() / 10) * 10).padStart(2, '0')}`,
    total: 0,
    anomalies: 0,
    anomalyRate: 0,
  };
});

export function AnomalyChart({ data, title = 'Anomaly Trends' }: AnomalyChartProps) {
  const formattedData = data.length > 0
    ? data.map((point) => ({
        ...point,
        time: format(new Date(point.timestamp), 'HH:mm'),
        anomalyRate: point.total > 0 ? (point.anomalies / point.total) * 100 : 0,
      }))
    : EMPTY_DATA;

  const isEmpty = data.length === 0;

  return (
    <div className="bg-soc-card rounded-xl border border-soc-border p-6">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
      <div className="h-64 relative">
        {isEmpty && (
          <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
            <span className="text-soc-text-muted text-sm bg-soc-card/80 px-3 py-1 rounded">No data yet</span>
          </div>
        )}
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={formattedData}>
            <defs>
              <linearGradient id="colorAnomalies" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#dc2626" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#dc2626" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0891b2" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#0891b2" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2e37" />
            <XAxis
              dataKey="time"
              stroke="#4b5563"
              tick={{ fill: '#9ca3af', fontSize: 10 }}
              axisLine={{ stroke: '#2a2e37' }}
              interval={Math.max(0, Math.floor(formattedData.length / 6) - 1)}
            />
            <YAxis
              stroke="#4b5563"
              tick={{ fill: '#9ca3af', fontSize: 11 }}
              axisLine={{ stroke: '#2a2e37' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1a1d23',
                border: '1px solid #2a2e37',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#e5e7eb' }}
            />
            <Area
              type="monotone"
              dataKey="total"
              stroke="#0891b2"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorTotal)"
              name="Total Events"
            />
            <Area
              type="monotone"
              dataKey="anomalies"
              stroke="#dc2626"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorAnomalies)"
              name="Anomalies"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default AnomalyChart;
