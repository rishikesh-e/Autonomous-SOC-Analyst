import {
  TrendingUp,
  TrendingDown,
  Shield,
  AlertTriangle,
  Target,
  Clock,
  Zap,
  BarChart3
} from 'lucide-react';
import type { DashboardMetrics, Incident } from '../types';
import { cn } from '../utils/helpers';

interface SecurityInsightsProps {
  metrics: DashboardMetrics | null;
  title?: string;
}

interface InsightItem {
  label: string;
  value: string | number;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  icon: React.ElementType;
  color: 'red' | 'amber' | 'emerald' | 'blue' | 'purple' | 'cyan';
}

const colorClasses = {
  red: 'text-red-400 bg-red-500/10',
  amber: 'text-amber-400 bg-amber-500/10',
  emerald: 'text-emerald-400 bg-emerald-500/10',
  blue: 'text-blue-400 bg-blue-500/10',
  purple: 'text-purple-400 bg-purple-500/10',
  cyan: 'text-cyan-400 bg-cyan-500/10',
};

export function SecurityInsights({ metrics, title = 'Security Insights' }: SecurityInsightsProps) {
  // Calculate insights from metrics
  const incidents = metrics?.recent_incidents || [];
  const severityDist = metrics?.severity_distribution || {};
  const statusDist = metrics?.status_distribution || {};

  // Calculate threat level
  const criticalCount = severityDist.CRITICAL || 0;
  const highCount = severityDist.HIGH || 0;
  const threatScore = Math.min(100, (criticalCount * 25 + highCount * 10));
  const threatLevel = threatScore >= 75 ? 'Critical' : threatScore >= 50 ? 'High' : threatScore >= 25 ? 'Medium' : 'Low';
  const threatColor = threatScore >= 75 ? 'red' : threatScore >= 50 ? 'amber' : threatScore >= 25 ? 'blue' : 'emerald';

  // Calculate response rate
  const totalIncidents = metrics?.total_incidents || 0;
  const resolvedCount = (statusDist.EXECUTED || 0) + (statusDist.RESOLVED || 0);
  const responseRate = totalIncidents > 0 ? Math.round((resolvedCount / totalIncidents) * 100) : 0;

  // Find most common attack type
  const attackTypes: Record<string, number> = {};
  incidents.forEach(inc => {
    const type = inc.classification?.attack_type || 'UNKNOWN';
    attackTypes[type] = (attackTypes[type] || 0) + 1;
  });
  const topAttackType = Object.entries(attackTypes)
    .sort(([, a], [, b]) => b - a)[0];
  const topAttackLabel = topAttackType
    ? topAttackType[0].replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())
    : 'None';

  // Calculate average confidence
  const confidences = incidents
    .filter(inc => inc.classification?.confidence)
    .map(inc => inc.classification!.confidence);
  const avgConfidence = confidences.length > 0
    ? Math.round((confidences.reduce((a, b) => a + b, 0) / confidences.length) * 100)
    : 0;

  // Recent activity (last hour)
  const now = Date.now();
  const recentIncidents = incidents.filter(inc => {
    const created = new Date(inc.created_at).getTime();
    return now - created < 60 * 60 * 1000; // Last hour
  });

  const insights: InsightItem[] = [
    {
      label: 'Threat Level',
      value: threatLevel,
      icon: Shield,
      color: threatColor as InsightItem['color'],
    },
    {
      label: 'Response Rate',
      value: `${responseRate}%`,
      trend: responseRate >= 70 ? 'up' : responseRate >= 40 ? 'neutral' : 'down',
      icon: Zap,
      color: responseRate >= 70 ? 'emerald' : responseRate >= 40 ? 'amber' : 'red',
    },
    {
      label: 'Top Attack Vector',
      value: topAttackLabel,
      icon: Target,
      color: 'purple',
    },
    {
      label: 'Detection Confidence',
      value: `${avgConfidence}%`,
      icon: BarChart3,
      color: avgConfidence >= 80 ? 'emerald' : avgConfidence >= 60 ? 'blue' : 'amber',
    },
    {
      label: 'Recent Activity',
      value: `${recentIncidents.length} incidents`,
      trendValue: 'Last hour',
      icon: Clock,
      color: recentIncidents.length > 5 ? 'red' : recentIncidents.length > 2 ? 'amber' : 'emerald',
    },
    {
      label: 'Critical Alerts',
      value: criticalCount,
      trend: criticalCount > 0 ? 'up' : 'neutral',
      icon: AlertTriangle,
      color: criticalCount > 0 ? 'red' : 'emerald',
    },
  ];

  return (
    <div className="bg-soc-card rounded-xl border border-soc-border p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <BarChart3 className="w-5 h-5 text-soc-text-muted" />
      </div>

      <div className="grid grid-cols-2 gap-3">
        {insights.map((insight, index) => (
          <div
            key={index}
            className="p-3 bg-soc-dark/50 rounded-lg border border-soc-border/50 hover:border-soc-border transition-colors"
          >
            <div className="flex items-start justify-between mb-2">
              <div className={cn('p-1.5 rounded-lg', colorClasses[insight.color])}>
                <insight.icon className="w-3.5 h-3.5" />
              </div>
              {insight.trend && (
                <div className={cn(
                  'flex items-center text-xs',
                  insight.trend === 'up' ? 'text-emerald-400' :
                  insight.trend === 'down' ? 'text-red-400' : 'text-soc-text-muted'
                )}>
                  {insight.trend === 'up' ? (
                    <TrendingUp className="w-3 h-3" />
                  ) : insight.trend === 'down' ? (
                    <TrendingDown className="w-3 h-3" />
                  ) : null}
                </div>
              )}
            </div>
            <div className="text-lg font-semibold text-white truncate">
              {insight.value}
            </div>
            <div className="text-xs text-soc-text-muted truncate">
              {insight.label}
            </div>
            {insight.trendValue && (
              <div className="text-xs text-soc-text-muted/70 mt-0.5">
                {insight.trendValue}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Quick Summary */}
      <div className="mt-4 p-3 bg-soc-dark/30 rounded-lg border border-soc-border/30">
        <div className="text-xs text-soc-text-muted mb-1">Quick Summary</div>
        <p className="text-sm text-soc-text">
          {threatScore >= 50 ? (
            <>
              <span className="text-amber-400 font-medium">Active threats detected.</span>
              {' '}Monitor {criticalCount + highCount} high-priority incidents requiring attention.
            </>
          ) : totalIncidents > 0 ? (
            <>
              <span className="text-emerald-400 font-medium">Security posture stable.</span>
              {' '}{responseRate}% of incidents resolved with {avgConfidence}% avg confidence.
            </>
          ) : (
            <>
              <span className="text-blue-400 font-medium">No active threats.</span>
              {' '}System monitoring active and ready for detection.
            </>
          )}
        </p>
      </div>
    </div>
  );
}

export default SecurityInsights;
