"""
Agent State definitions for LangGraph
"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
import operator

from backend.models.schemas import (
    AnomalyResult, ThreatClassification, RecommendedAction,
    Incident, IncidentStatus, SeverityLevel, AttackType, ActionType
)


class AgentState(TypedDict):
    """State shared between all agents in the workflow"""
    # Input
    anomaly: AnomalyResult
    raw_logs: List[Dict[str, Any]]

    # Agent outputs
    log_analysis: Optional[Dict[str, Any]]
    threat_classification: Optional[ThreatClassification]
    recommended_actions: List[RecommendedAction]
    selected_action: Optional[RecommendedAction]
    decision_reasoning: Optional[str]

    # Execution
    execution_result: Optional[Dict[str, Any]]
    incident_status: IncidentStatus

    # Metadata
    agent_logs: Annotated[List[Dict[str, Any]], operator.add]
    incident_id: Optional[str]
    requires_human_approval: bool
    human_feedback: Optional[str]
    error: Optional[str]

    # Multi-tenancy
    tenant_context: Optional[Dict[str, Any]]


def create_initial_state(
    anomaly: AnomalyResult,
    raw_logs: List[Dict[str, Any]],
    tenant_context: Optional[Dict[str, Any]] = None
) -> AgentState:
    """Create initial state for the agent workflow"""
    return AgentState(
        anomaly=anomaly,
        raw_logs=raw_logs,
        log_analysis=None,
        threat_classification=None,
        recommended_actions=[],
        selected_action=None,
        decision_reasoning=None,
        execution_result=None,
        incident_status=IncidentStatus.DETECTED,
        agent_logs=[],
        incident_id=None,
        requires_human_approval=True,
        human_feedback=None,
        error=None,
        tenant_context=tenant_context
    )
