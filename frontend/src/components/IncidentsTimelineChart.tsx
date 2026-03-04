import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { TrendingUp } from 'lucide-react';
import type { Incident } from '../types';

interface IncidentsTimelineChartProps {
  incidents: Incident[];
  title?: string;
}

interface TimelineDataPoint {
  time: string;
  pending: number;
  approved: number;
  rejected: number;
  total: number;
}

// Empty data shows last 12 hours
const EMPTY_DATA = Array.from({ length: 12 }, (_, i) => {
  const now = new Date();
  const hoursAgo = 11 - i;
  const time = new Date(now.getTime() - hoursAgo * 60 * 60 * 1000);
  return {
    time: `${time.getMonth() + 1}/${time.getDate()} ${time.getHours()}:00`,
    pending: 0,
    approved: 0,
    rejected: 0,
    total: 0,
  };
});

export function IncidentsTimelineChart({
  incidents,
  title = 'Incidents Over Time',
}: IncidentsTimelineChartProps) {
  const timelineData = React.useMemo(() => {
    if (!incidents.length) return [];

    // Group incidents by hour
    const hourlyData: Record<string, TimelineDataPoint> = {};

    incidents.forEach((incident) => {
      const date = new Date(incident.created_at);
      const hourKey = `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`;

      if (!hourlyData[hourKey]) {
        hourlyData[hourKey] = {
          time: hourKey,
          pending: 0,
          approved: 0,
          rejected: 0,
          total: 0,
        };
      }

      const status = incident.status?.toLowerCase() || 'pending';
      if (status === 'pending' || status === 'pending_approval') {
        hourlyData[hourKey].pending++;
      } else if (status === 'approved' || status === 'resolved') {
        hourlyData[hourKey].approved++;
      } else if (status === 'rejected') {
        hourlyData[hourKey].rejected++;
      }
      hourlyData[hourKey].total++;
    });

    // Sort by time and return last 24 data points
    const currentYear = new Date().getFullYear();
    return Object.values(hourlyData)
      .sort((a, b) => {
        const parseTime = (t: string) => {
          const [datePart, timePart] = t.split(' ');
          const [month, day] = datePart.split('/').map(Number);
          const hour = parseInt(timePart);
          return new Date(currentYear, month - 1, day, hour).getTime();
        };
        return parseTime(a.time) - parseTime(b.time);
      })
      .slice(-24);
  }, [incidents]);

  const isEmpty = timelineData.length === 0;
  const chartData = isEmpty ? EMPTY_DATA : timelineData;

  return (
    <div className="bg-soc-card rounded-xl border border-soc-border p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <TrendingUp className="w-5 h-5 text-soc-text-muted" />
      </div>
      <div className="h-64 relative">
        {isEmpty && (
          <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
            <span className="text-soc-text-muted text-sm bg-soc-card/80 px-3 py-1 rounded">No data yet</span>
          </div>
        )}
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorPending" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#d97706" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#d97706" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorApproved" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#059669" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#059669" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorRejected" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#dc2626" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#dc2626" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2e37" />
            <XAxis
              dataKey="time"
              stroke="#4b5563"
              tick={{ fill: '#9ca3af', fontSize: 10 }}
              axisLine={{ stroke: '#2a2e37' }}
              interval={Math.max(0, Math.floor(chartData.length / 6) - 1)}
              angle={-45}
              textAnchor="end"
              height={50}
            />
            <YAxis
              stroke="#4b5563"
              tick={{ fill: '#9ca3af', fontSize: 11 }}
              axisLine={{ stroke: '#2a2e37' }}
            />
            {!isEmpty && (
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1a1d23',
                  border: '1px solid #2a2e37',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: '#e5e7eb' }}
              />
            )}
            <Legend
              verticalAlign="top"
              height={36}
              formatter={(value) => (
                <span className="text-soc-text-muted text-xs capitalize">{value}</span>
              )}
            />
            <Area
              type="monotone"
              dataKey="pending"
              stackId="1"
              stroke="#d97706"
              fill="url(#colorPending)"
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="approved"
              stackId="1"
              stroke="#059669"
              fill="url(#colorApproved)"
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="rejected"
              stackId="1"
              stroke="#dc2626"
              fill="url(#colorRejected)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default IncidentsTimelineChart;
