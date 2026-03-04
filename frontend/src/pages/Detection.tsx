import React, { useState, useCallback } from 'react';
import {
  Zap,
  RefreshCw,
  Play,
  Square,
  Target,
  AlertTriangle,
  CheckCircle,
  Bot,
  Brain,
} from 'lucide-react';
import { usePolling } from '../hooks/usePolling';
import {
  getSystemStatus,
  processIncident,
  trainDetector,
  simulateAttack,
  startDetection,
  stopDetection,
  createAutonomousIncident,
} from '../utils/api';
import type { SystemStatus } from '../types';
import { cn, formatPercentage } from '../utils/helpers';

const attackScenarios = [
  { value: 'brute_force', label: 'Brute Force', description: 'Simulate credential stuffing attack' },
  { value: 'ddos', label: 'DDoS', description: 'Simulate distributed denial of service' },
  { value: 'recon', label: 'Reconnaissance', description: 'Simulate port/path scanning' },
  { value: 'injection', label: 'Injection', description: 'Simulate SQL injection attempts' },
  { value: 'suspicious', label: 'Suspicious IP', description: 'Simulate suspicious IP behavior' },
  { value: 'mixed', label: 'Mixed Attack', description: 'Combination of multiple attacks' },
];

export function Detection() {
  const [isDetecting, setIsDetecting] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isCreatingAutonomous, setIsCreatingAutonomous] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const [selectedScenario, setSelectedScenario] = useState('brute_force');

  const { data: status, refetch: refetchStatus } = usePolling<SystemStatus>({
    fetcher: getSystemStatus,
    interval: 5000,
  });

  const handleRunDetection = useCallback(async () => {
    setIsDetecting(true);
    setLastResult(null);
    try {
      const result = await processIncident(5);
      if (result.incident) {
        setLastResult(`Incident created: ${result.incident.id?.slice(0, 8)} - ${result.incident.classification?.attack_type || 'Unknown'}`);
      } else {
        setLastResult(result.message || 'No anomalies detected');
      }
    } catch (error) {
      setLastResult(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsDetecting(false);
    }
  }, []);

  const handleTrainModel = useCallback(async () => {
    setIsTraining(true);
    setLastResult(null);
    try {
      const result = await trainDetector(24);

      // Check the actual status returned by the API
      if (result.status === 'success' && (result.windows_trained ?? 0) > 0) {
        setLastResult(`✓ Training complete: ${result.windows_trained} windows processed`);
      } else if (result.status === 'insufficient_data') {
        const timeWindowLogs = result.time_window_logs ?? result.log_count ?? 0;
        const totalLogs = result.log_count ?? 0;
        setLastResult(`⚠ Insufficient data: Only ${totalLogs} logs found (need at least 100).\n\nTo generate logs, run:\npython scripts/log_generator.py -m continuous -r 10 -p 0.15`);
      } else if (result.status === 'no_valid_windows') {
        setLastResult(`⚠ No valid training windows: Logs found but couldn't create training windows. Need more continuous log data.`);
      } else if ((result.windows_trained ?? 0) === 0) {
        setLastResult(`⚠ Training failed: No windows processed. Ensure logs are being ingested into Elasticsearch.`);
      } else {
        setLastResult(`Training status: ${result.status}`);
      }
      refetchStatus();
    } catch (error) {
      setLastResult(`✗ Training error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsTraining(false);
    }
  }, [refetchStatus]);

  const handleSimulateAttack = useCallback(async () => {
    setIsSimulating(true);
    setLastResult(null);
    try {
      const result = await simulateAttack(selectedScenario);
      setLastResult(`Attack simulated: ${result.scenario} - ${result.output || 'Logs generated'}`);
    } catch (error) {
      setLastResult(`Simulation error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsSimulating(false);
    }
  }, [selectedScenario]);

  const handleToggleDetection = useCallback(async () => {
    try {
      if (status?.detection_running) {
        await stopDetection();
      } else {
        await startDetection();
      }
      refetchStatus();
    } catch (error) {
      console.error('Failed to toggle detection:', error);
    }
  }, [status, refetchStatus]);

  const handleAutonomousIncident = useCallback(async () => {
    setIsCreatingAutonomous(true);
    setLastResult(null);
    try {
      const result = await createAutonomousIncident();
      const autoStatus = result.auto_executed ? '🤖 AUTO-EXECUTED' : '👤 Needs Review';
      setLastResult(
        `${autoStatus}\n` +
        `Incident: ${result.incident_id.slice(0, 8)}\n` +
        `Type: ${result.attack_type} | Severity: ${result.severity}\n` +
        `Action: ${result.action_taken} (Confidence: ${(result.confidence * 100).toFixed(0)}%)\n` +
        `Reasoning: ${result.reasoning}`
      );
    } catch (error) {
      setLastResult(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsCreatingAutonomous(false);
    }
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Anomaly Detection</h1>
        <p className="text-soc-text-muted mt-1">
          Configure and control the ML-based anomaly detection system
        </p>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <StatusCard
          title="Autonomous Mode"
          status={true}
          statusLabel="Active"
          icon={Brain}
          highlight
        />
        <StatusCard
          title="Detection Service"
          status={status?.detection_running}
          statusLabel={status?.detection_running ? 'Running' : 'Stopped'}
          icon={Zap}
        />
        <StatusCard
          title="ML Model"
          status={status?.anomaly_detector === 'ready'}
          statusLabel={status?.anomaly_detector === 'ready' ? 'Trained' : 'Not Trained'}
          icon={Target}
        />
        <StatusCard
          title="Groq API"
          status={status?.groq_api === 'configured'}
          statusLabel={status?.groq_api === 'configured' ? 'Connected' : 'Not Configured'}
          icon={CheckCircle}
        />
      </div>

      {/* Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Detection Control */}
        <div className="bg-soc-card rounded-xl border border-soc-border p-6">
          <h3 className="text-lg font-semibold mb-4">Detection Control</h3>
          <div className="space-y-4">
            <button
              onClick={handleToggleDetection}
              className={cn(
                'w-full flex items-center justify-center space-x-2 px-4 py-3 rounded-lg font-medium transition-colors',
                status?.detection_running
                  ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                  : 'bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30'
              )}
            >
              {status?.detection_running ? (
                <>
                  <Square className="w-5 h-5" />
                  <span>Stop Continuous Detection</span>
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  <span>Start Continuous Detection</span>
                </>
              )}
            </button>

            <button
              onClick={handleRunDetection}
              disabled={isDetecting}
              className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-soc-accent rounded-lg font-medium hover:bg-blue-600 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={cn('w-5 h-5', isDetecting && 'animate-spin')} />
              <span>{isDetecting ? 'Detecting...' : 'Run Detection Now'}</span>
            </button>

            <button
              onClick={handleTrainModel}
              disabled={isTraining}
              className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-purple-500/20 text-purple-400 rounded-lg font-medium hover:bg-purple-500/30 transition-colors disabled:opacity-50"
            >
              <Target className={cn('w-5 h-5', isTraining && 'animate-spin')} />
              <span>{isTraining ? 'Training...' : 'Train ML Model'}</span>
            </button>

            <div className="border-t border-soc-border pt-4 mt-4">
              <p className="text-xs text-soc-text-muted mb-3">Autonomous Mode Demo</p>
              <button
                onClick={handleAutonomousIncident}
                disabled={isCreatingAutonomous}
                className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-gradient-to-r from-purple-600/30 to-blue-600/30 border border-purple-500/30 text-purple-300 rounded-lg font-medium hover:from-purple-600/40 hover:to-blue-600/40 transition-colors disabled:opacity-50"
              >
                <Bot className={cn('w-5 h-5', isCreatingAutonomous && 'animate-pulse')} />
                <span>{isCreatingAutonomous ? 'AI Processing...' : 'Create Autonomous Incident'}</span>
              </button>
              <p className="text-xs text-soc-text-muted mt-2 text-center">
                Simulates an attack and lets AI autonomously decide and execute response
              </p>
            </div>
          </div>
        </div>

        {/* Attack Simulation */}
        <div className="bg-soc-card rounded-xl border border-soc-border p-6">
          <h3 className="text-lg font-semibold mb-4">Attack Simulation</h3>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              {attackScenarios.map((scenario) => (
                <button
                  key={scenario.value}
                  onClick={() => setSelectedScenario(scenario.value)}
                  className={cn(
                    'p-3 rounded-lg text-left transition-colors',
                    selectedScenario === scenario.value
                      ? 'bg-orange-500/20 border border-orange-500/50'
                      : 'bg-soc-dark hover:bg-soc-border'
                  )}
                >
                  <p className="font-medium text-sm">{scenario.label}</p>
                  <p className="text-xs text-soc-text-muted mt-1">{scenario.description}</p>
                </button>
              ))}
            </div>

            <button
              onClick={handleSimulateAttack}
              disabled={isSimulating}
              className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-orange-500/20 text-orange-400 rounded-lg font-medium hover:bg-orange-500/30 transition-colors disabled:opacity-50"
            >
              <AlertTriangle className={cn('w-5 h-5', isSimulating && 'animate-pulse')} />
              <span>{isSimulating ? 'Simulating...' : 'Simulate Attack'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Result */}
      {lastResult && (
        <div className={cn(
          'rounded-xl border p-6',
          lastResult.includes('AUTO-EXECUTED')
            ? 'bg-gradient-to-r from-purple-900/20 to-blue-900/20 border-purple-500/30'
            : 'bg-soc-card border-soc-border'
        )}>
          <div className="flex items-center space-x-2 mb-2">
            {lastResult.includes('AUTO-EXECUTED') && <Bot className="w-5 h-5 text-purple-400" />}
            <h3 className="text-lg font-semibold">Last Result</h3>
          </div>
          <pre className="text-soc-text font-mono text-sm whitespace-pre-wrap">{lastResult}</pre>
        </div>
      )}

      {/* Feature Importance */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <h3 className="text-lg font-semibold mb-4">Feature Importance</h3>
        <div className="space-y-3">
          {[
            { name: 'Failed Login Ratio', importance: 0.18 },
            { name: 'IP Frequency', importance: 0.15 },
            { name: 'Request Burst Rate', importance: 0.15 },
            { name: 'Geo Anomaly Score', importance: 0.12 },
            { name: 'Status Code Entropy', importance: 0.10 },
            { name: 'Unique Paths Ratio', importance: 0.10 },
            { name: 'Time Deviation', importance: 0.08 },
            { name: 'Error Rate', importance: 0.07 },
            { name: 'Avg Latency', importance: 0.05 },
          ].map((feature) => (
            <div key={feature.name} className="flex items-center space-x-4">
              <span className="w-40 text-sm text-soc-text-muted">{feature.name}</span>
              <div className="flex-1 bg-soc-border rounded-full h-2">
                <div
                  className="bg-soc-accent h-2 rounded-full"
                  style={{ width: `${feature.importance * 100}%` }}
                />
              </div>
              <span className="w-12 text-sm text-right">
                {formatPercentage(feature.importance)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatusCard({
  title,
  status,
  statusLabel,
  icon: Icon,
  highlight,
}: {
  title: string;
  status?: boolean;
  statusLabel: string;
  icon: React.ElementType;
  highlight?: boolean;
}) {
  return (
    <div className={cn(
      'rounded-xl border p-6',
      highlight
        ? 'bg-gradient-to-br from-purple-900/30 to-blue-900/30 border-purple-500/30'
        : 'bg-soc-card border-soc-border'
    )}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-soc-text-muted">{title}</p>
          <p
            className={cn(
              'text-lg font-semibold mt-1',
              highlight ? 'text-purple-400' : status ? 'text-emerald-400' : 'text-soc-text-muted'
            )}
          >
            {statusLabel}
          </p>
        </div>
        <div
          className={cn(
            'p-3 rounded-lg',
            highlight
              ? 'bg-purple-600/20 text-purple-400'
              : status ? 'bg-emerald-600/20 text-emerald-400' : 'bg-soc-dark text-soc-text-muted'
          )}
        >
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
}

export default Detection;
