import React from 'react';
import { Bot, Clock, CheckCircle, XCircle, AlertCircle, Brain, Shield, Zap, ChevronDown, ChevronUp } from 'lucide-react';
import type { AgentLog } from '../types';
import { cn, formatDate } from '../utils/helpers';

interface AgentLogsPanelProps {
  logs: AgentLog[];
  title?: string;
  maxHeight?: string;
}

const agentColors: Record<string, string> = {
  LogAnalysisAgent: 'text-cyan-400 bg-cyan-600/15',
  ThreatClassificationAgent: 'text-violet-400 bg-violet-600/15',
  DecisionAgent: 'text-orange-400 bg-orange-600/15',
  AutonomousDecisionAgent: 'text-orange-400 bg-orange-600/15',
  ResponseAgent: 'text-emerald-400 bg-emerald-600/15',
  AutonomousResponseAgent: 'text-emerald-400 bg-emerald-600/15',
  HumanApproval: 'text-amber-400 bg-amber-600/15',
};

const resultIcons: Record<string, React.ReactNode> = {
  success: <CheckCircle className="w-4 h-4 text-emerald-400" />,
  failed: <XCircle className="w-4 h-4 text-red-400" />,
  skipped: <AlertCircle className="w-4 h-4 text-soc-text-muted" />,
  awaiting_approval: <Clock className="w-4 h-4 text-amber-400" />,
  pending_review: <Clock className="w-4 h-4 text-amber-400" />,
  auto_approved: <Zap className="w-4 h-4 text-purple-400" />,
  approved: <CheckCircle className="w-4 h-4 text-emerald-400" />,
  denied: <XCircle className="w-4 h-4 text-red-400" />,
};

// Helper to check if log has decision details
const hasDecisionDetails = (log: AgentLog): boolean => {
  return log.agent === 'AutonomousDecisionAgent' || log.agent === 'DecisionAgent';
};

// Helper to get confidence color
const getConfidenceColor = (confidence: number): string => {
  if (confidence >= 0.85) return 'text-emerald-400';
  if (confidence >= 0.7) return 'text-amber-400';
  return 'text-red-400';
};

export function AgentLogsPanel({
  logs,
  title = 'Agent Decision Logs',
  maxHeight = '400px',
}: AgentLogsPanelProps) {
  const [expandedLogs, setExpandedLogs] = React.useState<Set<number>>(new Set());

  const toggleExpanded = (index: number) => {
    setExpandedLogs(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  return (
    <div className="bg-soc-card rounded-xl border border-soc-border p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <Bot className="w-5 h-5 text-soc-text-muted" />
      </div>

      {logs.length === 0 ? (
        <div className="text-center py-8 text-soc-text-muted">
          <Bot className="w-8 h-8 mx-auto mb-2" />
          <p>No agent logs available</p>
        </div>
      ) : (
        <div
          className="space-y-2 overflow-y-auto pr-2"
          style={{ maxHeight }}
        >
          {logs.map((log, index) => {
            const isDecisionLog = hasDecisionDetails(log);
            const isExpanded = expandedLogs.has(index);
            const confidence = log.confidence as number | undefined;
            const selectedAction = log.selected_action as string | undefined;
            const autoApproveReason = log.auto_approve_reason as string | undefined;
            const reasoning = log.reasoning as string | undefined;
            const learningContext = log.learning_context as { similar_incidents?: number; known_ips?: number; recent_accuracy?: number } | undefined;

            return (
              <div
                key={`${log.timestamp}-${index}`}
                className="border border-soc-border rounded-lg p-4 hover:border-soc-text-muted/30 transition-colors bg-soc-dark/30"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <span
                      className={cn(
                        'px-2 py-1 rounded text-xs font-medium',
                        agentColors[log.agent] || 'text-soc-text-muted bg-soc-dark'
                      )}
                    >
                      {log.agent.replace('Autonomous', '')}
                    </span>
                    <span className="text-xs text-soc-text-muted">
                      {log.action}
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    {resultIcons[log.result] || resultIcons.success}
                    <span className={cn(
                      'text-xs',
                      log.result === 'auto_approved' ? 'text-purple-400' : 'text-soc-text-muted'
                    )}>
                      {log.result === 'auto_approved' ? 'Auto-Approved' :
                       log.result === 'pending_review' ? 'Needs Review' : log.result}
                    </span>
                  </div>
                </div>

                {/* Decision Details Section */}
                {isDecisionLog && (
                  <div className="mb-3 space-y-2">
                    {/* Confidence and Action Row */}
                    <div className="flex items-center flex-wrap gap-2">
                      {confidence !== undefined && (
                        <div className="flex items-center space-x-1.5 bg-soc-dark/50 px-2 py-1 rounded">
                          <Brain className="w-3.5 h-3.5 text-soc-text-muted" />
                          <span className="text-xs text-soc-text-muted">Confidence:</span>
                          <span className={cn('text-xs font-medium', getConfidenceColor(confidence))}>
                            {(confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      )}
                      {selectedAction && (
                        <div className="flex items-center space-x-1.5 bg-soc-dark/50 px-2 py-1 rounded">
                          <Shield className="w-3.5 h-3.5 text-soc-text-muted" />
                          <span className="text-xs text-soc-text-muted">Action:</span>
                          <span className="text-xs font-medium text-soc-accent">
                            {selectedAction.replace('_', ' ')}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Auto-Approve Reason */}
                    {autoApproveReason && (
                      <div className="bg-soc-dark/30 border border-soc-border/50 rounded px-3 py-2">
                        <span className="text-xs text-soc-text-muted">Decision: </span>
                        <span className="text-xs text-soc-text">{autoApproveReason}</span>
                      </div>
                    )}

                    {/* Expandable Reasoning Section */}
                    {reasoning && (
                      <button
                        onClick={() => toggleExpanded(index)}
                        className="flex items-center space-x-1 text-xs text-soc-accent hover:text-soc-accent-light transition-colors"
                      >
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        <span>{isExpanded ? 'Hide' : 'Show'} Full Reasoning</span>
                      </button>
                    )}

                    {isExpanded && reasoning && (
                      <div className="bg-soc-dark/50 border border-soc-border/50 rounded px-3 py-2 mt-2">
                        <p className="text-xs text-soc-text whitespace-pre-wrap leading-relaxed">
                          {reasoning}
                        </p>
                      </div>
                    )}

                    {/* Learning Context */}
                    {learningContext && (
                      <div className="flex items-center flex-wrap gap-2 text-xs">
                        {learningContext.similar_incidents !== undefined && (
                          <span className="text-soc-text-muted">
                            Similar incidents: <span className="text-soc-text">{learningContext.similar_incidents}</span>
                          </span>
                        )}
                        {learningContext.known_ips !== undefined && learningContext.known_ips > 0 && (
                          <span className="text-soc-text-muted">
                            | Known IPs: <span className="text-amber-400">{learningContext.known_ips}</span>
                          </span>
                        )}
                        {learningContext.recent_accuracy !== undefined && (
                          <span className="text-soc-text-muted">
                            | Accuracy: <span className={getConfidenceColor(learningContext.recent_accuracy)}>
                              {(learningContext.recent_accuracy * 100).toFixed(0)}%
                            </span>
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {log.summary && (
                  <p className="text-sm text-soc-text mb-2">{log.summary}</p>
                )}

                <div className="flex items-center justify-between text-xs text-soc-text-muted">
                  <span>{formatDate(log.timestamp)}</span>
                  {log.duration_ms !== undefined && (
                    <span>{log.duration_ms.toFixed(0)}ms</span>
                  )}
                </div>

                {log.incident_id && (
                  <div className="mt-2 text-xs">
                    <span className="text-soc-text-muted">Incident: </span>
                    <span className="font-mono text-soc-accent">
                      {log.incident_id.slice(0, 8)}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default AgentLogsPanel;
