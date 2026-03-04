import React from 'react';
import { Settings as SettingsIcon, Server, Brain, Key, Clock } from 'lucide-react';
import { usePolling } from '../hooks/usePolling';
import { getSystemStatus } from '../utils/api';
import type { SystemStatus } from '../types';
import { cn } from '../utils/helpers';

export function Settings() {
  const { data: status } = usePolling<SystemStatus>({
    fetcher: getSystemStatus,
    interval: 10000,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-soc-text-muted mt-1">
          Configure the SOC Analyst system
        </p>
      </div>

      {/* System Status */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <Server className="w-5 h-5 text-soc-text-muted" />
          <span>System Status</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <StatusItem
            label="Elasticsearch"
            value={status?.elasticsearch || 'Unknown'}
            status={status?.elasticsearch === 'connected'}
          />
          <StatusItem
            label="Anomaly Detector"
            value={status?.anomaly_detector || 'Unknown'}
            status={status?.anomaly_detector === 'ready'}
          />
          <StatusItem
            label="Groq API"
            value={status?.groq_api || 'Unknown'}
            status={status?.groq_api === 'configured'}
          />
          <StatusItem
            label="Detection Service"
            value={status?.detection_running ? 'Running' : 'Stopped'}
            status={status?.detection_running}
          />
        </div>
      </div>

      {/* Configuration */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <SettingsIcon className="w-5 h-5 text-soc-text-muted" />
          <span>Configuration</span>
        </h3>
        <div className="space-y-4">
          <ConfigItem
            icon={Server}
            label="Elasticsearch Host"
            value="http://localhost:9200"
            description="Elasticsearch server URL"
          />
          <ConfigItem
            icon={Key}
            label="Groq API Key"
            value={status?.groq_api === 'configured' ? '••••••••••••' : 'Not configured'}
            description="API key for Groq LLM"
          />
          <ConfigItem
            icon={Brain}
            label="ML Model"
            value="Isolation Forest"
            description="Anomaly detection algorithm"
          />
          <ConfigItem
            icon={Clock}
            label="Detection Window"
            value="5 minutes"
            description="Time window for anomaly detection"
          />
        </div>
      </div>

      {/* Agent Configuration */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <Brain className="w-5 h-5 text-soc-text-muted" />
          <span>Agent Configuration</span>
        </h3>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-soc-dark/50 rounded-lg p-4">
              <p className="font-medium text-blue-400">Log Analysis Agent</p>
              <p className="text-sm text-soc-text-muted mt-1">
                Analyzes raw logs and extracts patterns
              </p>
            </div>
            <div className="bg-soc-dark/50 rounded-lg p-4">
              <p className="font-medium text-purple-400">Threat Classification Agent</p>
              <p className="text-sm text-soc-text-muted mt-1">
                Classifies threats using MITRE ATT&CK
              </p>
            </div>
            <div className="bg-soc-dark/50 rounded-lg p-4">
              <p className="font-medium text-orange-400">Decision Agent</p>
              <p className="text-sm text-soc-text-muted mt-1">
                Determines appropriate response actions
              </p>
            </div>
            <div className="bg-soc-dark/50 rounded-lg p-4">
              <p className="font-medium text-emerald-400">Response Agent</p>
              <p className="text-sm text-soc-text-muted mt-1">
                Executes approved defensive actions
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Human-in-the-Loop */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <h3 className="text-lg font-semibold mb-4">Human-in-the-Loop Settings</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-soc-dark/50 rounded-lg">
            <div>
              <p className="font-medium">Require Approval</p>
              <p className="text-sm text-soc-text-muted">
                All actions require human approval before execution
              </p>
            </div>
            <div className="w-12 h-6 bg-emerald-600 rounded-full relative">
              <div className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full" />
            </div>
          </div>
          <div className="flex items-center justify-between p-4 bg-soc-dark/50 rounded-lg">
            <div>
              <p className="font-medium">Auto-approve Low Severity</p>
              <p className="text-sm text-soc-text-muted">
                Automatically approve monitoring actions for low severity threats
              </p>
            </div>
            <div className="w-12 h-6 bg-soc-border rounded-full relative">
              <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full" />
            </div>
          </div>
        </div>
      </div>

      {/* About */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <h3 className="text-lg font-semibold mb-4">About</h3>
        <div className="space-y-2 text-sm text-soc-text-muted">
          <p>Autonomous SOC Analyst v1.0.0</p>
          <p>Powered by LangGraph + Groq LLM</p>
          <p>ML Engine: scikit-learn Isolation Forest</p>
          <p>Log Ingestion: Fluent Bit + Elasticsearch</p>
        </div>
      </div>
    </div>
  );
}

function StatusItem({
  label,
  value,
  status,
}: {
  label: string;
  value: string;
  status?: boolean;
}) {
  return (
    <div className="flex items-center justify-between p-3 bg-soc-dark/50 rounded-lg">
      <span className="text-soc-text-muted">{label}</span>
      <div className="flex items-center space-x-2">
        <div
          className={cn(
            'w-2 h-2 rounded-full',
            status ? 'bg-emerald-600' : 'bg-red-500'
          )}
        />
        <span className={status ? 'text-emerald-400' : 'text-red-400'}>
          {value}
        </span>
      </div>
    </div>
  );
}

function ConfigItem({
  icon: Icon,
  label,
  value,
  description,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  description: string;
}) {
  return (
    <div className="flex items-start space-x-4 p-4 bg-soc-dark/50 rounded-lg">
      <Icon className="w-5 h-5 text-soc-text-muted mt-0.5" />
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <p className="font-medium">{label}</p>
          <p className="text-sm text-soc-accent font-mono">{value}</p>
        </div>
        <p className="text-sm text-soc-text-muted mt-1">{description}</p>
      </div>
    </div>
  );
}

export default Settings;
