import React from 'react';
import { cn } from '../utils/helpers';
import type { LucideIcon } from 'lucide-react';

interface StatsCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'teal';
}

const colorStyles = {
  blue: 'border-blue-600/30',
  green: 'border-emerald-600/30',
  yellow: 'border-amber-600/30',
  red: 'border-red-600/30',
  purple: 'border-violet-600/30',
  teal: 'border-cyan-600/30',
};

const iconStyles = {
  blue: 'bg-blue-600/15 text-blue-400',
  green: 'bg-emerald-600/15 text-emerald-400',
  yellow: 'bg-amber-600/15 text-amber-400',
  red: 'bg-red-600/15 text-red-400',
  purple: 'bg-violet-600/15 text-violet-400',
  teal: 'bg-cyan-600/15 text-cyan-400',
};

const valueStyles = {
  blue: 'text-blue-400',
  green: 'text-emerald-400',
  yellow: 'text-amber-400',
  red: 'text-red-400',
  purple: 'text-violet-400',
  teal: 'text-cyan-400',
};

export function StatsCard({
  title,
  value,
  icon: Icon,
  trend,
  color = 'teal',
}: StatsCardProps) {
  return (
    <div
      className={cn(
        'bg-soc-card rounded-xl border border-soc-border p-5 transition-all hover:border-opacity-50',
        colorStyles[color]
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-soc-text-muted mb-2">{title}</p>
          <p className={cn('text-3xl font-semibold', valueStyles[color])}>{value}</p>
          {trend && (
            <p
              className={cn(
                'text-sm mt-2',
                trend.isPositive ? 'text-emerald-400' : 'text-red-400'
              )}
            >
              {trend.isPositive ? '+' : ''}
              {trend.value}% from last hour
            </p>
          )}
        </div>
        <div className={cn('p-3 rounded-lg', iconStyles[color])}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}

export default StatsCard;
