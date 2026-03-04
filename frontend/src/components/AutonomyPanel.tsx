import React from 'react';
import { Brain, Zap, Target, AlertTriangle, CheckCircle } from 'lucide-react';
import { usePolling } from '../hooks/usePolling';
import { getAutonomyStatus } from '../utils/api';
import type { AutonomyStatus } from '../types';
import { cn, formatPercentage } from '../utils/helpers';

export function AutonomyPanel() {
  const { data: status } = usePolling<AutonomyStatus>({
    fetcher: getAutonomyStatus,
    interval: 5000,
  });

  if (!status) {
    return (
      <div className="bg-soc-card rounded-xl border border-soc-border p-6 animate-pulse">
        <div className="h-6 bg-soc-dark rounded w-1/3 mb-4" />
        <div className="h-20 bg-soc-dark rounded" />
      </div>
    );
  }

  const autoApproveRate = status.auto_approve_rate * 100;
  const accuracy = status.recent_accuracy * 100;

  return (
    <div className="bg-soc-card rounded-xl border border-soc-border p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className={cn(
            'p-2 rounded-lg',
            status.autonomous_mode ? 'bg-emerald-600/20' : 'bg-amber-600/20'
          )}>
            <Brain className={cn(
              'w-6 h-6',
              status.autonomous_mode ? 'text-emerald-400' : 'text-amber-400'
            )} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Autonomous Mode</h3>
            <p className="text-sm text-soc-text-muted">
              {status.autonomous_mode ? 'AI is making decisions autonomously' : 'Human approval required'}
            </p>
          </div>
        </div>
        <div className={cn(
          'px-3 py-1 rounded-full text-sm font-medium',
          status.autonomous_mode
            ? 'bg-emerald-600/20 text-emerald-400'
            : 'bg-amber-600/20 text-amber-400'
        )}>
          {status.autonomous_mode ? 'ACTIVE' : 'SUPERVISED'}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard
          icon={Zap}
          label="Auto-Approved"
          value={`${autoApproveRate.toFixed(1)}%`}
          subtext={`${status.auto_approved}/${status.total_decisions} decisions`}
          color="blue"
        />
        <StatCard
          icon={Target}
          label="Accuracy"
          value={`${accuracy.toFixed(1)}%`}
          subtext="Recent decisions"
          color={accuracy >= 90 ? 'emerald' : accuracy >= 70 ? 'amber' : 'red'}
        />
        <StatCard
          icon={AlertTriangle}
          label="False Positives"
          value={String(status.false_positives)}
          subtext="Over-reactions"
          color="amber"
        />
        <StatCard
          icon={CheckCircle}
          label="Confidence Threshold"
          value={formatPercentage(status.auto_approve_threshold)}
          subtext="Auto-approve if above"
          color="purple"
        />
      </div>

      {/* Learning Progress */}
      <div className="border-t border-soc-border pt-4">
        <h4 className="text-sm font-medium text-soc-text-muted mb-3">Learning Progress</h4>
        <div className="space-y-3">
          <LearningBar
            label="Auth Failure Threshold"
            value={status.learned_thresholds?.auth_failure_threshold || 10}
            max={20}
            unit=" failures"
          />
          <LearningBar
            label="Burst Rate Threshold"
            value={status.learned_thresholds?.burst_rate_threshold || 10}
            max={50}
            unit=" req/s"
          />
          <LearningBar
            label="Auto-Approve Confidence"
            value={(status.learned_thresholds?.confidence_auto_approve || 0.75) * 100}
            max={100}
            unit="%"
          />
        </div>
      </div>

      {/* Decision Flow */}
      <div className="border-t border-soc-border pt-4 mt-4">
        <h4 className="text-sm font-medium text-soc-text-muted mb-3">Decision Flow</h4>
        <div className="flex items-center justify-between text-xs">
          <div className="flex flex-col items-center">
            <div className="w-10 h-10 rounded-full bg-blue-600/20 flex items-center justify-center mb-1">
              <span className="text-blue-400 font-bold">{status.total_decisions}</span>
            </div>
            <span className="text-soc-text-muted">Total</span>
          </div>
          <div className="flex-1 h-0.5 bg-soc-border mx-2" />
          <div className="flex flex-col items-center">
            <div className="w-10 h-10 rounded-full bg-emerald-600/20 flex items-center justify-center mb-1">
              <span className="text-emerald-400 font-bold">{status.auto_approved}</span>
            </div>
            <span className="text-soc-text-muted">Auto</span>
          </div>
          <div className="flex-1 h-0.5 bg-soc-border mx-2" />
          <div className="flex flex-col items-center">
            <div className="w-10 h-10 rounded-full bg-amber-600/20 flex items-center justify-center mb-1">
              <span className="text-amber-400 font-bold">{status.total_decisions - status.auto_approved}</span>
            </div>
            <span className="text-soc-text-muted">Review</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  subtext,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  subtext: string;
  color: 'blue' | 'emerald' | 'amber' | 'red' | 'purple';
}) {
  const colors = {
    blue: 'bg-blue-600/20 text-blue-400',
    emerald: 'bg-emerald-600/20 text-emerald-400',
    amber: 'bg-amber-600/20 text-amber-400',
    red: 'bg-red-600/20 text-red-400',
    purple: 'bg-purple-600/20 text-purple-400',
  };

  return (
    <div className="bg-soc-dark rounded-lg p-3">
      <div className="flex items-center space-x-2 mb-2">
        <div className={cn('p-1.5 rounded', colors[color])}>
          <Icon className="w-4 h-4" />
        </div>
        <span className="text-xs text-soc-text-muted">{label}</span>
      </div>
      <p className="text-xl font-bold text-white">{value}</p>
      <p className="text-xs text-soc-text-muted">{subtext}</p>
    </div>
  );
}

function LearningBar({
  label,
  value,
  max,
  unit,
}: {
  label: string;
  value: number;
  max: number;
  unit: string;
}) {
  const percentage = Math.min(100, (value / max) * 100);

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-soc-text-muted">{label}</span>
        <span className="text-soc-text">{value.toFixed(1)}{unit}</span>
      </div>
      <div className="h-2 bg-soc-dark rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-blue-600 to-purple-600 rounded-full transition-all duration-500"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

export default AutonomyPanel;
