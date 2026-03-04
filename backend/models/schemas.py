"""
Pydantic schemas for the SOC Analyst system
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    ANALYZING = "ANALYZING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXECUTED = "EXECUTED"
    RESOLVED = "RESOLVED"


class AttackType(str, Enum):
    BRUTE_FORCE = "BRUTE_FORCE"
    RECONNAISSANCE = "RECONNAISSANCE"
    DDOS = "DDOS"
    INJECTION = "INJECTION"
    ANOMALOUS_TRAFFIC = "ANOMALOUS_TRAFFIC"
    SUSPICIOUS_IP = "SUSPICIOUS_IP"
    AUTH_FAILURE = "AUTH_FAILURE"
    UNKNOWN = "UNKNOWN"


class ActionType(str, Enum):
    BLOCK_IP = "BLOCK_IP"
    RATE_LIMIT = "RATE_LIMIT"
    ALERT = "ALERT"
    ESCALATE = "ESCALATE"
    MONITOR = "MONITOR"
    NO_ACTION = "NO_ACTION"


class LogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    client_ip: str
    method: str
    path: str
    status_code: int
    latency_ms: float
    user_agent: Optional[str] = None
    request_size_bytes: int = 0
    response_size_bytes: int = 0
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    geo_country: Optional[str] = None
    geo_city: Optional[str] = None
    is_authenticated: bool = False
    error_message: Optional[str] = None


class AnomalyFeatures(BaseModel):
    ip_frequency: float = Field(description="Request frequency from IP")
    failed_login_ratio: float = Field(description="Ratio of failed logins")
    time_deviation: float = Field(description="Deviation from normal time patterns")
    status_code_entropy: float = Field(description="Entropy of status codes")
    request_burst_rate: float = Field(description="Request burst rate")
    geo_anomaly_score: float = Field(description="Geographic anomaly score")
    unique_paths_ratio: float = Field(description="Unique paths requested ratio")
    avg_latency: float = Field(description="Average response latency")
    error_rate: float = Field(description="Error rate percentage")


class AnomalyResult(BaseModel):
    id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    anomaly_score: float
    is_anomaly: bool
    features: AnomalyFeatures
    source_ips: List[str]
    affected_paths: List[str]
    raw_log_ids: List[str] = []
    window_start: datetime
    window_end: datetime


class ThreatClassification(BaseModel):
    attack_type: AttackType
    confidence: float = Field(ge=0, le=1)
    severity: SeverityLevel
    indicators: List[str]
    mitre_techniques: List[str] = []


class RecommendedAction(BaseModel):
    action_type: ActionType
    target: str
    parameters: Dict[str, Any] = {}
    reasoning: str
    confidence: float = Field(ge=0, le=1)


class Incident(BaseModel):
    id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: IncidentStatus = IncidentStatus.DETECTED
    anomaly: AnomalyResult
    classification: Optional[ThreatClassification] = None
    recommended_actions: List[RecommendedAction] = []
    selected_action: Optional[RecommendedAction] = None
    decision_reasoning: Optional[str] = None
    agent_logs: List[Dict[str, Any]] = []
    human_feedback: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None


class IncidentApproval(BaseModel):
    incident_id: str
    approved: bool
    feedback: Optional[str] = None
    modified_action: Optional[RecommendedAction] = None


class DashboardMetrics(BaseModel):
    total_incidents: int
    pending_approval: int
    blocked_ips: int
    anomaly_rate: float
    severity_distribution: Dict[str, int]
    recent_incidents: List[Incident]
    top_risky_ips: List[Dict[str, Any]]
    time_series_anomalies: List[Dict[str, Any]]


class EvaluationMetrics(BaseModel):
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    false_positive_rate: float
    detection_latency_ms: float
    total_samples: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int


class TenantContext(BaseModel):
    """
    Context object for multi-tenant operations.
    Provides organization-scoped index names and user context.
    """
    org_id: str
    org_slug: str
    user_id: str
    user_role: str

    @property
    def logs_index(self) -> str:
        """Index name for logs"""
        return f"soc-logs-{self.org_id}"

    @property
    def logs_index_pattern(self) -> str:
        """Pattern for logs indices (for Logstash-style date-based indices)"""
        return f"soc-logs-{self.org_id}*"

    @property
    def anomalies_index(self) -> str:
        """Index name for anomalies"""
        return f"soc-anomalies-{self.org_id}"

    @property
    def incidents_index(self) -> str:
        """Index name for incidents"""
        return f"soc-incidents-{self.org_id}"

    @property
    def metrics_index(self) -> str:
        """Index name for metrics"""
        return f"soc-metrics-{self.org_id}"

    def get_index_name(self, base_name: str) -> str:
        """Get tenant-scoped index name for any base index name"""
        return f"{base_name}-{self.org_id}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "org_id": self.org_id,
            "org_slug": self.org_slug,
            "user_id": self.user_id,
            "user_role": self.user_role
        }
