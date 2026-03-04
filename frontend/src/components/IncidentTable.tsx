import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Clock, CheckCircle, XCircle, Eye, FileWarning, Bot, User, ThumbsUp, ThumbsDown, ChevronDown, ChevronUp, Brain, Shield } from 'lucide-react';
import type { Incident } from '../types';
import { submitFeedback } from '../utils/api';
import {
  cn,
  formatRelativeTime,
  getSeverityColor,
  getStatusColor,
  getAttackTypeLabel,
  formatPercentage,
} from '../utils/helpers';

interface IncidentTableProps {
  incidents: Incident[];
  onApprove?: (id: string) => void;
  onDeny?: (id: string) => void;
  showActions?: boolean;
  title?: string;
}

export function IncidentTable({
  incidents,
  onApprove,
  onDeny,
  showActions = true,
  title = 'Recent Incidents',
}: IncidentTableProps) {
  const navigate = useNavigate();
  const [feedbackSent, setFeedbackSent] = useState<Record<string, 'correct' | 'incorrect' | null>>({});
  const [expandedIncidents, setExpandedIncidents] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    setExpandedIncidents(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  const handleFeedback = async (incidentId: string, wasCorrect: boolean) => {
    try {
      await submitFeedback(incidentId, wasCorrect, !wasCorrect, false);
      setFeedbackSent(prev => ({ ...prev, [incidentId]: wasCorrect ? 'correct' : 'incorrect' }));
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  const isAutoExecuted = (incident: Incident): boolean => {
    return incident.status === 'EXECUTED' &&
      (incident.classification?.confidence || 0) >= 0.75;
  };

  if (incidents.length === 0) {
    return (
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <FileWarning className="w-5 h-5 text-soc-text-muted" />
        </div>
        <div className="text-center py-8 text-soc-text-muted">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
          <p>No incidents found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-soc-card rounded-xl border border-soc-border overflow-hidden">
      <div className="flex items-center justify-between p-6 pb-0">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <FileWarning className="w-5 h-5 text-soc-text-muted" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-soc-border bg-soc-dark/50">
              <th className="text-left p-4 text-xs font-semibold text-soc-text-muted uppercase tracking-wider">
                ID
              </th>
              <th className="text-left p-4 text-xs font-semibold text-soc-text-muted uppercase tracking-wider">
                Type
              </th>
              <th className="text-left p-4 text-xs font-semibold text-soc-text-muted uppercase tracking-wider">
                Severity
              </th>
              <th className="text-left p-4 text-xs font-semibold text-soc-text-muted uppercase tracking-wider">
                Status
              </th>
              <th className="text-left p-4 text-xs font-semibold text-soc-text-muted uppercase tracking-wider">
                Mode
              </th>
              <th className="text-left p-4 text-xs font-semibold text-soc-text-muted uppercase tracking-wider">
                Confidence
              </th>
              <th className="text-left p-4 text-xs font-semibold text-soc-text-muted uppercase tracking-wider">
                Source IPs
              </th>
              <th className="text-left p-4 text-xs font-semibold text-soc-text-muted uppercase tracking-wider">
                Time
              </th>
              {showActions && (
                <th className="text-left p-4 text-xs font-semibold text-soc-text-muted uppercase tracking-wider">
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {incidents.map((incident) => {
              const isExpanded = incident.id ? expandedIncidents.has(incident.id) : false;
              const hasReasoning = incident.decision_reasoning || incident.selected_action;
              const colSpan = showActions ? 9 : 8;

              return (
                <>
                <tr
                  key={incident.id}
                  className="border-b border-soc-border/50 hover:bg-soc-dark/30 transition-colors"
                >
                  <td className="p-4">
                    <div className="flex items-center space-x-2">
                      {hasReasoning && (
                        <button
                          onClick={() => incident.id && toggleExpanded(incident.id)}
                          className="p-1 hover:bg-soc-dark rounded transition-colors"
                          title={isExpanded ? 'Hide reasoning' : 'Show reasoning'}
                        >
                          {isExpanded ? (
                            <ChevronUp className="w-4 h-4 text-soc-text-muted" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-soc-text-muted" />
                          )}
                        </button>
                      )}
                      <button
                        onClick={() => navigate(`/incidents/${incident.id}`)}
                        className="text-soc-accent hover:text-soc-accent-light font-mono text-sm transition-colors"
                      >
                        {incident.id?.slice(0, 8) || 'N/A'}
                      </button>
                    </div>
                  </td>
                <td className="p-4">
                  <span className="text-sm text-soc-text">
                    {incident.classification
                      ? getAttackTypeLabel(incident.classification.attack_type)
                      : 'Unknown'}
                  </span>
                </td>
                <td className="p-4">
                  {incident.classification && (
                    <span
                      className={cn(
                        'px-2.5 py-1 rounded text-xs font-medium',
                        getSeverityColor(incident.classification.severity)
                      )}
                    >
                      {incident.classification.severity}
                    </span>
                  )}
                </td>
                <td className="p-4">
                  <span
                    className={cn(
                      'px-2.5 py-1 rounded text-xs font-medium',
                      getStatusColor(incident.status)
                    )}
                  >
                    {incident.status.replace('_', ' ')}
                  </span>
                </td>
                <td className="p-4">
                  <div className={cn(
                    'flex items-center space-x-1.5 px-2 py-1 rounded-lg text-xs font-medium w-fit',
                    isAutoExecuted(incident)
                      ? 'bg-purple-600/20 text-purple-400'
                      : 'bg-blue-600/20 text-blue-400'
                  )}>
                    {isAutoExecuted(incident) ? (
                      <>
                        <Bot className="w-3.5 h-3.5" />
                        <span>Auto</span>
                      </>
                    ) : (
                      <>
                        <User className="w-3.5 h-3.5" />
                        <span>Manual</span>
                      </>
                    )}
                  </div>
                </td>
                <td className="p-4">
                  <div className="flex items-center space-x-2">
                    <div className="w-16 bg-soc-dark rounded-full h-1.5">
                      <div
                        className="bg-soc-accent h-1.5 rounded-full"
                        style={{
                          width: `${(incident.classification?.confidence || 0) * 100}%`,
                        }}
                      />
                    </div>
                    <span className="text-sm text-soc-text-muted">
                      {formatPercentage(incident.classification?.confidence || 0)}
                    </span>
                  </div>
                </td>
                <td className="p-4">
                  <div className="flex flex-wrap gap-1">
                    {incident.anomaly.source_ips.slice(0, 2).map((ip) => (
                      <span
                        key={ip}
                        className="bg-soc-dark px-2 py-1 rounded text-xs font-mono text-soc-text-muted"
                      >
                        {ip}
                      </span>
                    ))}
                    {incident.anomaly.source_ips.length > 2 && (
                      <span className="text-xs text-soc-text-muted">
                        +{incident.anomaly.source_ips.length - 2}
                      </span>
                    )}
                  </div>
                </td>
                <td className="p-4">
                  <div className="flex items-center space-x-2 text-sm text-soc-text-muted">
                    <Clock className="w-4 h-4" />
                    <span>{formatRelativeTime(incident.created_at)}</span>
                  </div>
                </td>
                {showActions && (
                  <td className="p-4">
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => navigate(`/incidents/${incident.id}`)}
                        className="p-2 hover:bg-soc-dark rounded-lg transition-colors"
                        title="View Details"
                      >
                        <Eye className="w-4 h-4 text-soc-text-muted hover:text-soc-text" />
                      </button>
                      {incident.status === 'PENDING_APPROVAL' && (
                        <>
                          <button
                            onClick={() => onApprove?.(incident.id!)}
                            className="p-2 hover:bg-emerald-600/20 rounded-lg transition-colors"
                            title="Approve"
                          >
                            <CheckCircle className="w-4 h-4 text-emerald-400" />
                          </button>
                          <button
                            onClick={() => onDeny?.(incident.id!)}
                            className="p-2 hover:bg-red-600/20 rounded-lg transition-colors"
                            title="Deny"
                          >
                            <XCircle className="w-4 h-4 text-red-400" />
                          </button>
                        </>
                      )}
                      {/* Feedback buttons for learning */}
                      {incident.status === 'EXECUTED' && incident.id && (
                        feedbackSent[incident.id] ? (
                          <span className={cn(
                            'px-2 py-1 rounded text-xs',
                            feedbackSent[incident.id] === 'correct'
                              ? 'bg-emerald-600/20 text-emerald-400'
                              : 'bg-red-600/20 text-red-400'
                          )}>
                            {feedbackSent[incident.id] === 'correct' ? 'Correct' : 'Incorrect'}
                          </span>
                        ) : (
                          <>
                            <button
                              onClick={() => handleFeedback(incident.id!, true)}
                              className="p-2 hover:bg-emerald-600/20 rounded-lg transition-colors"
                              title="Mark as correct decision"
                            >
                              <ThumbsUp className="w-4 h-4 text-emerald-400" />
                            </button>
                            <button
                              onClick={() => handleFeedback(incident.id!, false)}
                              className="p-2 hover:bg-red-600/20 rounded-lg transition-colors"
                              title="Mark as incorrect (false positive)"
                            >
                              <ThumbsDown className="w-4 h-4 text-red-400" />
                            </button>
                          </>
                        )
                      )}
                    </div>
                  </td>
                )}
              </tr>
              {/* Expandable Reasoning Row */}
              {isExpanded && hasReasoning && (
                <tr key={`${incident.id}-details`} className="bg-soc-dark/50 border-b border-soc-border/50">
                  <td colSpan={colSpan} className="p-4">
                    <div className="space-y-4">
                      {/* Selected Action */}
                      {incident.selected_action && (
                        <div className="flex items-start space-x-3">
                          <Shield className="w-5 h-5 text-soc-accent mt-0.5" />
                          <div className="flex-1">
                            <h4 className="text-sm font-medium text-white mb-1">Selected Action</h4>
                            <div className="flex items-center flex-wrap gap-2">
                              <span className="bg-soc-accent/20 text-soc-accent px-2 py-1 rounded text-sm font-medium">
                                {incident.selected_action.action_type.replace('_', ' ')}
                              </span>
                              <span className="text-sm text-soc-text-muted">
                                Target: <span className="font-mono text-soc-text">{incident.selected_action.target}</span>
                              </span>
                              <span className="text-sm text-soc-text-muted">
                                Confidence: <span className={cn(
                                  'font-medium',
                                  incident.selected_action.confidence >= 0.85 ? 'text-emerald-400' :
                                  incident.selected_action.confidence >= 0.7 ? 'text-amber-400' : 'text-red-400'
                                )}>
                                  {(incident.selected_action.confidence * 100).toFixed(0)}%
                                </span>
                              </span>
                            </div>
                            {incident.selected_action.reasoning && (
                              <p className="text-sm text-soc-text-muted mt-2">
                                {incident.selected_action.reasoning}
                              </p>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Decision Reasoning */}
                      {incident.decision_reasoning && (
                        <div className="flex items-start space-x-3">
                          <Brain className="w-5 h-5 text-orange-400 mt-0.5" />
                          <div className="flex-1">
                            <h4 className="text-sm font-medium text-white mb-1">Decision Reasoning</h4>
                            <div className="bg-soc-dark/50 border border-soc-border/50 rounded-lg p-3">
                              <p className="text-sm text-soc-text whitespace-pre-wrap leading-relaxed">
                                {incident.decision_reasoning}
                              </p>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Threat Indicators */}
                      {incident.classification?.indicators && incident.classification.indicators.length > 0 && (
                        <div className="flex items-start space-x-3">
                          <AlertTriangle className="w-5 h-5 text-amber-400 mt-0.5" />
                          <div className="flex-1">
                            <h4 className="text-sm font-medium text-white mb-1">Threat Indicators</h4>
                            <ul className="list-disc list-inside space-y-1">
                              {incident.classification.indicators.slice(0, 5).map((indicator, idx) => (
                                <li key={idx} className="text-sm text-soc-text-muted">{indicator}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              )}
              </>
            );
          })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default IncidentTable;
