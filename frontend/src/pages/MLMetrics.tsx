import React, { useState } from 'react';
import {
  Brain,
  Activity,
  Target,
  Clock,
  RefreshCw,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { usePolling } from '../hooks/usePolling';
import { getEvaluationMetrics, getEvaluationResults } from '../utils/api';
import type { EvaluationMetrics } from '../types';
import { cn } from '../utils/helpers';

interface EvaluationResult {
  name: string;
  timestamp: string;
  metrics: EvaluationMetrics;
}

export function MLMetrics() {
  const [isRunning, setIsRunning] = useState(false);
  const [mode, setMode] = useState<'holdout' | 'elasticsearch_holdout' | 'cross_validation'>('holdout');
  const [samples, setSamples] = useState(100);
  const [attackRatio, setAttackRatio] = useState(0.1);

  const { data: resultsData, refetch: refetchResults } = usePolling<{
    results: EvaluationResult[];
  }>({
    fetcher: getEvaluationResults,
    interval: 30000,
  });

  const latestMetrics = resultsData?.results?.[0]?.metrics || null;

  const runEvaluation = async () => {
    setIsRunning(true);
    try {
      await getEvaluationMetrics(mode, samples, attackRatio);
      await refetchResults();
    } catch (error) {
      console.error('Evaluation failed:', error);
    } finally {
      setIsRunning(false);
    }
  };

  // Check for overfitting indicators
  const isPerfectScore = latestMetrics &&
    latestMetrics.f1_score === 1.0 &&
    latestMetrics.false_positives === 0 &&
    latestMetrics.false_negatives === 0;

  const confusionMatrix = latestMetrics
    ? [
        { name: 'True Positive', value: latestMetrics.true_positives, color: '#059669' },
        { name: 'False Positive', value: latestMetrics.false_positives, color: '#dc2626' },
        { name: 'True Negative', value: latestMetrics.true_negatives, color: '#0891b2' },
        { name: 'False Negative', value: latestMetrics.false_negatives, color: '#d97706' },
      ]
    : [];

  const radarData = latestMetrics
    ? [
        { metric: 'Precision', value: latestMetrics.precision * 100, fullMark: 100 },
        { metric: 'Recall', value: latestMetrics.recall * 100, fullMark: 100 },
        { metric: 'F1 Score', value: latestMetrics.f1_score * 100, fullMark: 100 },
        { metric: 'ROC-AUC', value: latestMetrics.roc_auc * 100, fullMark: 100 },
        {
          metric: 'Specificity',
          value: (1 - latestMetrics.false_positive_rate) * 100,
          fullMark: 100,
        },
      ]
    : [];

  const historyData =
    resultsData?.results?.slice(0, 10).map((r) => ({
      name: new Date(r.timestamp).toLocaleTimeString(),
      f1: r.metrics.f1_score * 100,
      precision: r.metrics.precision * 100,
      recall: r.metrics.recall * 100,
    })) || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">ML Model Performance</h1>
          <p className="text-soc-text-muted mt-1">
            Anomaly detection model evaluation metrics
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex flex-col">
            <label className="text-xs text-soc-text-muted mb-1">Mode</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as 'holdout' | 'elasticsearch_holdout' | 'cross_validation')}
              className="bg-soc-dark border border-soc-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soc-accent"
            >
              <option value="holdout">Holdout (Recommended)</option>
              <option value="elasticsearch_holdout">ES Temporal Split</option>
              <option value="cross_validation">Cross-Validation</option>
            </select>
          </div>
          <div className="flex flex-col">
            <label className="text-xs text-soc-text-muted mb-1">Samples</label>
            <input
              type="number"
              value={samples}
              onChange={(e) => setSamples(Number(e.target.value))}
              min={20}
              max={500}
              className="w-20 bg-soc-dark border border-soc-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soc-accent"
            />
          </div>
          <div className="flex flex-col">
            <label className="text-xs text-soc-text-muted mb-1">Attack %</label>
            <input
              type="number"
              value={attackRatio * 100}
              onChange={(e) => setAttackRatio(Number(e.target.value) / 100)}
              min={5}
              max={50}
              step={5}
              className="w-16 bg-soc-dark border border-soc-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-soc-accent"
            />
          </div>
          <button
            onClick={runEvaluation}
            disabled={isRunning}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors mt-5',
              isRunning
                ? 'bg-soc-border text-soc-text-muted cursor-not-allowed'
                : 'bg-soc-accent text-white hover:bg-soc-accent-light'
            )}
          >
            <RefreshCw className={cn('w-4 h-4', isRunning && 'animate-spin')} />
            {isRunning ? 'Running...' : 'Run Evaluation'}
          </button>
        </div>
      </div>

      {/* Overfitting Warning */}
      {isPerfectScore && (
        <div className="bg-amber-900/30 border border-amber-600/50 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold text-amber-400">Potential Overfitting Detected</h4>
            <p className="text-sm text-soc-text-muted mt-1">
              Perfect scores (100% F1, 0 FP, 0 FN) often indicate the model is evaluating on training data
              or test data is too easy. Use <strong>Holdout</strong> or <strong>Cross-Validation</strong> mode
              with realistic attack ratios (10-15%) for accurate performance estimates.
            </p>
          </div>
        </div>
      )}

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <MetricCard
          icon={Target}
          label="Precision"
          value={latestMetrics ? `${(latestMetrics.precision * 100).toFixed(1)}%` : '--'}
          description="Positive predictive value"
          status={latestMetrics && latestMetrics.precision >= 0.8 ? 'good' : 'warning'}
        />
        <MetricCard
          icon={Activity}
          label="Recall"
          value={latestMetrics ? `${(latestMetrics.recall * 100).toFixed(1)}%` : '--'}
          description="True positive rate"
          status={latestMetrics && latestMetrics.recall >= 0.8 ? 'good' : 'warning'}
        />
        <MetricCard
          icon={TrendingUp}
          label="F1 Score"
          value={latestMetrics ? `${(latestMetrics.f1_score * 100).toFixed(1)}%` : '--'}
          description="Harmonic mean"
          status={latestMetrics && latestMetrics.f1_score >= 0.8 ? 'good' : 'warning'}
        />
        <MetricCard
          icon={Brain}
          label="ROC-AUC"
          value={latestMetrics ? `${(latestMetrics.roc_auc * 100).toFixed(1)}%` : '--'}
          description="Area under curve"
          status={latestMetrics && latestMetrics.roc_auc >= 0.85 ? 'good' : 'warning'}
        />
        <MetricCard
          icon={AlertTriangle}
          label="FPR"
          value={
            latestMetrics
              ? `${(latestMetrics.false_positive_rate * 100).toFixed(1)}%`
              : '--'
          }
          description="False positive rate"
          status={
            latestMetrics && latestMetrics.false_positive_rate <= 0.1 ? 'good' : 'warning'
          }
        />
        <MetricCard
          icon={Clock}
          label="Latency"
          value={
            latestMetrics ? `${latestMetrics.detection_latency_ms.toFixed(0)}ms` : '--'
          }
          description="Detection latency"
          status={
            latestMetrics && latestMetrics.detection_latency_ms <= 100 ? 'good' : 'warning'
          }
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Radar Chart */}
        <div className="bg-soc-card rounded-xl border border-soc-border p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Brain className="w-5 h-5 text-soc-text-muted" />
            Performance Overview
          </h3>
          <div className="h-72">
            {radarData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#2a2e37" />
                  <PolarAngleAxis
                    dataKey="metric"
                    tick={{ fill: '#9ca3af', fontSize: 11 }}
                  />
                  <PolarRadiusAxis
                    angle={30}
                    domain={[0, 100]}
                    tick={{ fill: '#9ca3af', fontSize: 10 }}
                  />
                  <Radar
                    name="Performance"
                    dataKey="value"
                    stroke="#0891b2"
                    fill="#0891b2"
                    fillOpacity={0.3}
                    strokeWidth={2}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1d23',
                      border: '1px solid #2a2e37',
                      borderRadius: '8px',
                    }}
                    formatter={(value: number) => [`${value.toFixed(1)}%`, 'Score']}
                  />
                </RadarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-soc-text-muted">
                Run evaluation to see results
              </div>
            )}
          </div>
        </div>

        {/* Confusion Matrix */}
        <div className="bg-soc-card rounded-xl border border-soc-border p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Target className="w-5 h-5 text-soc-text-muted" />
            Confusion Matrix
          </h3>
          <div className="h-72">
            {confusionMatrix.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={confusionMatrix}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                    labelLine={{ stroke: '#4b5563' }}
                  >
                    {confusionMatrix.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1d23',
                      border: '1px solid #2a2e37',
                      borderRadius: '8px',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-soc-text-muted">
                Run evaluation to see results
              </div>
            )}
          </div>
          {latestMetrics && (
            <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-emerald-600" />
                <span className="text-soc-text-muted">True Positives:</span>
                <span className="font-medium">{latestMetrics.true_positives}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-red-600" />
                <span className="text-soc-text-muted">False Positives:</span>
                <span className="font-medium">{latestMetrics.false_positives}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-cyan-600" />
                <span className="text-soc-text-muted">True Negatives:</span>
                <span className="font-medium">{latestMetrics.true_negatives}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-amber-600" />
                <span className="text-soc-text-muted">False Negatives:</span>
                <span className="font-medium">{latestMetrics.false_negatives}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Historical Performance */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-soc-text-muted" />
          Historical Performance
        </h3>
        <div className="h-64">
          {historyData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={historyData.reverse()}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2e37" />
                <XAxis
                  dataKey="name"
                  stroke="#4b5563"
                  tick={{ fill: '#9ca3af', fontSize: 10 }}
                  axisLine={{ stroke: '#2a2e37' }}
                />
                <YAxis
                  domain={[0, 100]}
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
                  formatter={(value: number) => [`${value.toFixed(1)}%`]}
                />
                <Bar dataKey="f1" name="F1 Score" fill="#0891b2" radius={[4, 4, 0, 0]} />
                <Bar
                  dataKey="precision"
                  name="Precision"
                  fill="#059669"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="recall"
                  name="Recall"
                  fill="#d97706"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-soc-text-muted">
              No historical data available
            </div>
          )}
        </div>
      </div>

      {/* Evaluation History Table */}
      {resultsData?.results && resultsData.results.length > 0 && (
        <div className="bg-soc-card rounded-xl border border-soc-border p-6">
          <h3 className="text-lg font-semibold mb-4">Evaluation History</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-soc-border">
                  <th className="text-left py-3 px-4 text-soc-text-muted font-medium">
                    Timestamp
                  </th>
                  <th className="text-left py-3 px-4 text-soc-text-muted font-medium">
                    Samples
                  </th>
                  <th className="text-left py-3 px-4 text-soc-text-muted font-medium">
                    Precision
                  </th>
                  <th className="text-left py-3 px-4 text-soc-text-muted font-medium">
                    Recall
                  </th>
                  <th className="text-left py-3 px-4 text-soc-text-muted font-medium">
                    F1 Score
                  </th>
                  <th className="text-left py-3 px-4 text-soc-text-muted font-medium">
                    ROC-AUC
                  </th>
                  <th className="text-left py-3 px-4 text-soc-text-muted font-medium">
                    Latency
                  </th>
                </tr>
              </thead>
              <tbody>
                {resultsData.results.slice(0, 10).map((result, index) => (
                  <tr
                    key={index}
                    className="border-b border-soc-border/50 hover:bg-soc-dark/30"
                  >
                    <td className="py-3 px-4">
                      {new Date(result.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-4">{result.metrics.total_samples}</td>
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'font-medium',
                          result.metrics.precision >= 0.8
                            ? 'text-emerald-400'
                            : 'text-amber-400'
                        )}
                      >
                        {(result.metrics.precision * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'font-medium',
                          result.metrics.recall >= 0.8
                            ? 'text-emerald-400'
                            : 'text-amber-400'
                        )}
                      >
                        {(result.metrics.recall * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'font-medium',
                          result.metrics.f1_score >= 0.8
                            ? 'text-emerald-400'
                            : 'text-amber-400'
                        )}
                      >
                        {(result.metrics.f1_score * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {(result.metrics.roc_auc * 100).toFixed(1)}%
                    </td>
                    <td className="py-3 px-4">
                      {result.metrics.detection_latency_ms.toFixed(0)}ms
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  description,
  status,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  description: string;
  status: 'good' | 'warning' | 'error';
}) {
  return (
    <div className="bg-soc-card rounded-xl border border-soc-border p-4">
      <div className="flex items-center justify-between mb-2">
        <Icon className="w-5 h-5 text-soc-text-muted" />
        {status === 'good' ? (
          <CheckCircle className="w-4 h-4 text-emerald-500" />
        ) : status === 'warning' ? (
          <AlertTriangle className="w-4 h-4 text-amber-500" />
        ) : (
          <XCircle className="w-4 h-4 text-red-500" />
        )}
      </div>
      <p
        className={cn(
          'text-2xl font-bold',
          status === 'good' && 'text-emerald-400',
          status === 'warning' && 'text-amber-400',
          status === 'error' && 'text-red-400'
        )}
      >
        {value}
      </p>
      <p className="text-sm font-medium text-white mt-1">{label}</p>
      <p className="text-xs text-soc-text-muted">{description}</p>
    </div>
  );
}

export default MLMetrics;
