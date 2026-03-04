import axios from 'axios';
import type {
  Incident,
  DashboardMetrics,
  SystemStatus,
  AgentLog,
  BlockedIP,
  Organization,
  OrganizationMembership,
  OrganizationInvitation,
  OrganizationRole,
  MemberWithUser,
} from '../types';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Token storage key
const TOKEN_KEY = 'soc_auth_token';

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear stored auth data
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem('soc_auth_user');

      // Redirect to login if not already there
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Health & Status
export const getHealth = () => api.get('/health');

export const getSystemStatus = async (): Promise<SystemStatus> => {
  const response = await api.get('/status');
  return response.data;
};

// Incidents
export const getIncidents = async (
  status?: string,
  limit = 50
): Promise<{ incidents: Incident[]; count: number }> => {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  params.append('limit', limit.toString());
  const response = await api.get(`/incidents?${params}`);
  return response.data;
};

export const getPendingIncidents = async (): Promise<{
  incidents: Incident[];
  count: number;
}> => {
  const response = await api.get('/incidents/pending');
  return response.data;
};

export const getIncident = async (id: string): Promise<{ incident: Incident }> => {
  const response = await api.get(`/incidents/${id}`);
  return response.data;
};

export const approveIncident = async (
  id: string,
  approved: boolean,
  feedback?: string
): Promise<{ incident: Incident }> => {
  const response = await api.post(`/incidents/${id}/approve`, {
    incident_id: id,
    approved,
    feedback,
  });
  return response.data;
};

// Anomaly Detection
export const detectAnomalies = async (
  windowMinutes = 5
): Promise<{ anomaly: unknown; log_count: number }> => {
  const response = await api.post(`/anomaly/detect?window_minutes=${windowMinutes}`);
  return response.data;
};

export const processIncident = async (
  windowMinutes = 5
): Promise<{ incident: Incident | null; message?: string }> => {
  const response = await api.post(`/incidents/process?window_minutes=${windowMinutes}`);
  return response.data;
};

export const trainDetector = async (
  hours = 24
): Promise<{
  status: string;
  windows_trained?: number;
  total_logs?: number;
  log_count?: number;
  time_window_logs?: number;
  windows_attempted?: number;
}> => {
  const response = await api.post(`/anomaly/train?hours=${hours}`);
  return response.data;
};

// Dashboard Metrics
export const getDashboardMetrics = async (): Promise<DashboardMetrics> => {
  const response = await api.get('/dashboard/metrics');
  return response.data;
};

export const getAgentLogs = async (
  incidentId?: string,
  limit = 50
): Promise<{ logs: AgentLog[] }> => {
  const params = new URLSearchParams();
  if (incidentId) params.append('incident_id', incidentId);
  params.append('limit', limit.toString());
  const response = await api.get(`/dashboard/agent-logs?${params}`);
  return response.data;
};

// Defensive Actions
export const getBlockedIPs = async (): Promise<{
  blocked_ips: BlockedIP[];
  count: number;
}> => {
  const response = await api.get('/actions/blocked-ips');
  return response.data;
};

export const getRateLimitedIPs = async (): Promise<{
  rate_limited: BlockedIP[];
  count: number;
}> => {
  const response = await api.get('/actions/rate-limited');
  return response.data;
};

export const unblockIP = async (ip: string): Promise<{ status: string }> => {
  const response = await api.delete(`/actions/blocked-ips/${ip}`);
  return response.data;
};

export const getAlerts = async (limit = 20): Promise<{ alerts: unknown[] }> => {
  const response = await api.get(`/actions/alerts?limit=${limit}`);
  return response.data;
};

// Detection Control
export const startDetection = async (): Promise<{ status: string }> => {
  const response = await api.post('/detection/start');
  return response.data;
};

export const stopDetection = async (): Promise<{ status: string }> => {
  const response = await api.post('/detection/stop');
  return response.data;
};

// Simulation
export const simulateAttack = async (
  scenario: string
): Promise<{ status: string; scenario: string; output: string }> => {
  const response = await api.post(`/simulate/attack?scenario=${scenario}`);
  return response.data;
};

// Evaluation Metrics
export const getEvaluationMetrics = async (
  mode: 'holdout' | 'elasticsearch_holdout' | 'cross_validation' = 'holdout',
  samples = 100,
  attackRatio = 0.1
): Promise<{ metrics: import('../types').EvaluationMetrics; cross_validation?: {
  f1_mean: number;
  f1_std: number;
  precision_mean: number;
  precision_std: number;
  recall_mean: number;
  recall_std: number;
  num_folds: number;
} }> => {
  const params = new URLSearchParams({
    mode,
    samples: samples.toString(),
    attack_ratio: attackRatio.toString()
  });
  const response = await api.get(`/evaluation/run?${params}`);
  return response.data;
};

export const getEvaluationResults = async (): Promise<{
  results: Array<{
    name: string;
    timestamp: string;
    metrics: import('../types').EvaluationMetrics;
  }>;
}> => {
  const response = await api.get('/evaluation/results');
  return response.data;
};

// Autonomy & Learning APIs
export const getLearningStats = async (): Promise<{
  memory_stats: import('../types').LearningStats;
  decision_stats: import('../types').DecisionStats;
  autonomous_mode: boolean;
  human_in_loop: boolean;
}> => {
  const response = await api.get('/learning/stats');
  return response.data;
};

export const getAutonomyStatus = async (): Promise<import('../types').AutonomyStatus> => {
  const response = await api.get('/autonomy/status');
  return response.data;
};

export const submitFeedback = async (
  incidentId: string,
  wasCorrect: boolean,
  wasFalsePositive = false,
  wasFalseNegative = false,
  feedback?: string
): Promise<{ status: string; message: string }> => {
  const params = new URLSearchParams({
    incident_id: incidentId,
    was_correct: String(wasCorrect),
    was_false_positive: String(wasFalsePositive),
    was_false_negative: String(wasFalseNegative),
  });
  if (feedback) params.append('feedback', feedback);
  const response = await api.post(`/learning/feedback?${params}`);
  return response.data;
};

export const createAutonomousIncident = async (): Promise<{
  status: string;
  incident_id: string;
  attack_type: string;
  severity: string;
  action_taken: string;
  auto_executed: boolean;
  confidence: number;
  reasoning: string;
}> => {
  const response = await api.post('/demo/autonomous-incident');
  return response.data;
};

// Organization APIs
export const getCurrentOrganization = async (): Promise<Organization> => {
  const response = await api.get('/organizations/current');
  return response.data;
};

export const getOrganizationMembers = async (): Promise<MemberWithUser[]> => {
  const response = await api.get('/organizations/members');
  return response.data;
};

export const inviteUser = async (
  email: string,
  role: OrganizationRole
): Promise<OrganizationInvitation> => {
  const response = await api.post('/organizations/invite', { email, role });
  return response.data;
};

export const acceptInvitation = async (token: string): Promise<OrganizationMembership> => {
  const response = await api.post(`/organizations/invite/${token}/accept`);
  return response.data;
};

export const removeMember = async (userId: string): Promise<void> => {
  await api.delete(`/organizations/members/${userId}`);
};

export const updateMemberRole = async (
  userId: string,
  role: OrganizationRole
): Promise<OrganizationMembership> => {
  const response = await api.patch(`/organizations/members/${userId}`, { role });
  return response.data;
};

export const getPendingInvitations = async (): Promise<OrganizationInvitation[]> => {
  const response = await api.get('/organizations/invitations');
  return response.data;
};

export const getMemberDetails = async (userId: string): Promise<{
  id: string;
  email: string;
  username: string;
}> => {
  const response = await api.get(`/users/${userId}`);
  return response.data;
};

export default api;
