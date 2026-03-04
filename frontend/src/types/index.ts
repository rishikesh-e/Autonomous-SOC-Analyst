// Type definitions for SOC Analyst Dashboard

// Authentication Types
export interface User {
  id: string;
  email: string;
  username: string;
  created_at: string;
  is_active: boolean;
  org_id?: string | null;
  org_role?: string | null;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  email: string;
  username: string;
  password: string;
}

export type SeverityLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type IncidentStatus =
  | 'DETECTED'
  | 'ANALYZING'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'DENIED'
  | 'EXECUTED'
  | 'RESOLVED';

export type AttackType =
  | 'BRUTE_FORCE'
  | 'RECONNAISSANCE'
  | 'DDOS'
  | 'INJECTION'
  | 'ANOMALOUS_TRAFFIC'
  | 'SUSPICIOUS_IP'
  | 'AUTH_FAILURE'
  | 'UNKNOWN';

export type ActionType =
  | 'BLOCK_IP'
  | 'RATE_LIMIT'
  | 'ALERT'
  | 'ESCALATE'
  | 'MONITOR'
  | 'NO_ACTION';

export interface AnomalyFeatures {
  ip_frequency: number;
  failed_login_ratio: number;
  time_deviation: number;
  status_code_entropy: number;
  request_burst_rate: number;
  geo_anomaly_score: number;
  unique_paths_ratio: number;
  avg_latency: number;
  error_rate: number;
}

export interface AnomalyResult {
  id?: string;
  timestamp: string;
  anomaly_score: number;
  is_anomaly: boolean;
  features: AnomalyFeatures;
  source_ips: string[];
  affected_paths: string[];
  window_start: string;
  window_end: string;
}

export interface ThreatClassification {
  attack_type: AttackType;
  confidence: number;
  severity: SeverityLevel;
  indicators: string[];
  mitre_techniques: string[];
}

export interface RecommendedAction {
  action_type: ActionType;
  target: string;
  parameters: Record<string, unknown>;
  reasoning: string;
  confidence: number;
}

export interface AgentLog {
  agent: string;
  timestamp: string;
  duration_ms?: number;
  action: string;
  result: string;
  summary?: string;
  incident_id?: string;
  [key: string]: unknown;
}

export interface Incident {
  id?: string;
  created_at: string;
  updated_at: string;
  status: IncidentStatus;
  anomaly: AnomalyResult;
  classification?: ThreatClassification;
  recommended_actions: RecommendedAction[];
  selected_action?: RecommendedAction;
  decision_reasoning?: string;
  agent_logs: AgentLog[];
  human_feedback?: string;
  execution_result?: Record<string, unknown>;
}

export interface DashboardMetrics {
  total_incidents: number;
  pending_approval: number;
  blocked_ips: number;
  critical_incidents?: number;
  logs_ingested_24h?: number;
  anomalies_detected?: number;
  severity_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  time_series_anomalies: TimeSeriesPoint[];
  top_risky_ips: RiskyIP[];
  recent_incidents: Incident[];
}

export interface TimeSeriesPoint {
  timestamp: string;
  total: number;
  anomalies: number;
}

export interface RiskyIP {
  ip: string;
  count: number;
}

export interface BlockedIP {
  ip: string;
  blocked_at: string;
  duration_hours: number;
  permanent: boolean;
  reason: string;
}

export interface SystemStatus {
  elasticsearch: string;
  anomaly_detector: string;
  groq_api: string;
  detection_running: boolean;
  pending_incidents: number;
}

export interface EvaluationMetrics {
  precision: number;
  recall: number;
  f1_score: number;
  roc_auc: number;
  false_positive_rate: number;
  detection_latency_ms: number;
  total_samples: number;
  true_positives: number;
  false_positives: number;
  true_negatives: number;
  false_negatives: number;
}

// Autonomy & Learning Types
export interface LearningStats {
  total_decisions: number;
  decisions_with_feedback: number;
  false_positives: number;
  false_negatives: number;
  learned_thresholds: Record<string, number>;
  action_effectiveness: Record<string, { success: number; failure: number; total: number }>;
  known_ips: number;
  recent_accuracy: number;
  auto_approve_threshold: number;
}

export interface AutonomyStatus {
  autonomous_mode: boolean;
  human_in_loop_enabled: boolean;
  auto_approve_threshold: number;
  total_decisions: number;
  auto_approved: number;
  auto_approve_rate: number;
  recent_accuracy: number;
  learned_thresholds: Record<string, number>;
  false_positives: number;
  false_negatives: number;
}

export interface DecisionStats {
  total_decisions: number;
  auto_approved: number;
  auto_approve_rate: number;
  learning_stats: LearningStats;
}

// Organization Types
export type OrganizationRole = 'OWNER' | 'ADMIN' | 'ANALYST' | 'VIEWER';

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  settings?: OrganizationSettings;
}

export interface OrganizationSettings {
  max_incidents_per_day?: number;
  auto_block_threshold?: number;
  notification_email?: string;
}

export interface OrganizationMembership {
  id: string;
  user_id: string;
  org_id: string;
  role: OrganizationRole;
  joined_at: string;
  invited_by?: string;
}

export interface OrganizationInvitation {
  id: string;
  org_id: string;
  email: string;
  role: OrganizationRole;
  token: string;
  created_at: string;
  expires_at: string;
  invited_by: string;
  accepted: boolean;
  accepted_at?: string;
}

export interface InvitationCreate {
  email: string;
  role: OrganizationRole;
}

export interface MemberWithUser extends OrganizationMembership {
  email: string;
  username: string;
}
