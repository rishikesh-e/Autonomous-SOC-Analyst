"""
LangGraph Workflow - Orchestrates the 4 SOC agents
"""
from typing import Dict, Any, List, Literal, Optional
from datetime import datetime
import json

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from backend.utils import utc_isoformat

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from config.settings import settings
from agents.agent_state import AgentState, create_initial_state
from agents.log_analysis_agent import log_analysis_agent
from agents.threat_classification_agent import threat_classification_agent
from agents.decision_agent import decision_agent
from agents.response_agent import response_agent
from backend.models.schemas import (
    AnomalyResult, Incident, IncidentStatus, IncidentApproval
)


class SOCWorkflow:
    """
    LangGraph workflow orchestrating 4 agents:
    1. Log Analysis Agent
    2. Threat Classification Agent
    3. Decision Agent
    4. Response Agent
    """

    def __init__(self):
        self.memory = MemorySaver()
        self.workflow = self._build_workflow()
        self.pending_incidents: Dict[str, AgentState] = {}

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)

        # Add nodes for each agent
        workflow.add_node("log_analysis", self._log_analysis_node)
        workflow.add_node("threat_classification", self._threat_classification_node)
        workflow.add_node("decision", self._decision_node)
        workflow.add_node("response", self._response_node)
        workflow.add_node("await_approval", self._await_approval_node)

        # Define edges
        workflow.set_entry_point("log_analysis")

        workflow.add_edge("log_analysis", "threat_classification")
        workflow.add_edge("threat_classification", "decision")

        # Conditional edge based on human approval requirement
        workflow.add_conditional_edges(
            "decision",
            self._should_await_approval,
            {
                "await": "await_approval",
                "execute": "response"
            }
        )

        workflow.add_edge("await_approval", END)
        workflow.add_edge("response", END)

        return workflow.compile(checkpointer=self.memory)

    def _log_analysis_node(self, state: AgentState) -> AgentState:
        """Log Analysis Agent node"""
        return log_analysis_agent.analyze(state)

    def _threat_classification_node(self, state: AgentState) -> AgentState:
        """Threat Classification Agent node"""
        return threat_classification_agent.classify(state)

    def _decision_node(self, state: AgentState) -> AgentState:
        """Decision Agent node"""
        return decision_agent.decide(state)

    def _response_node(self, state: AgentState) -> AgentState:
        """Response Agent node"""
        return response_agent.execute(state)

    def _await_approval_node(self, state: AgentState) -> AgentState:
        """Store state for human approval"""
        incident_id = state.get('incident_id') or f"INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        state['incident_id'] = incident_id
        self.pending_incidents[incident_id] = state
        return state

    def _should_await_approval(self, state: AgentState) -> Literal["await", "execute"]:
        """Determine if we should wait for human approval"""
        if state.get('requires_human_approval', True):
            return "await"
        return "execute"

    def process_anomaly(
        self,
        anomaly: AnomalyResult,
        raw_logs: List[Dict[str, Any]],
        tenant_context: Optional[Dict[str, Any]] = None
    ) -> Incident:
        """Process an anomaly through the full workflow"""
        # Create initial state with tenant context
        initial_state = create_initial_state(anomaly, raw_logs, tenant_context)

        # Run the workflow
        config = {"configurable": {"thread_id": f"anomaly-{datetime.utcnow().timestamp()}"}}
        final_state = None

        for output in self.workflow.stream(initial_state, config):
            for node_name, state in output.items():
                final_state = state
                print(f"[{node_name}] completed")

        if not final_state:
            final_state = initial_state

        # Create incident from final state
        return self._state_to_incident(final_state)

    def approve_incident(self, approval: IncidentApproval) -> Incident:
        """Process human approval for a pending incident"""
        incident_id = approval.incident_id

        if incident_id not in self.pending_incidents:
            raise ValueError(f"Incident {incident_id} not found in pending incidents")

        state = self.pending_incidents[incident_id]

        # Update state based on approval
        if approval.approved:
            state['incident_status'] = IncidentStatus.APPROVED
            state['human_feedback'] = approval.feedback

            # Modify action if provided
            if approval.modified_action:
                state['selected_action'] = approval.modified_action

            # Execute the action
            state = response_agent.execute(state)
        else:
            state['incident_status'] = IncidentStatus.DENIED
            state['human_feedback'] = approval.feedback

        # Remove from pending
        del self.pending_incidents[incident_id]

        # Log approval
        state['agent_logs'] = state.get('agent_logs', []) + [{
            'agent': 'HumanApproval',
            'timestamp': utc_isoformat(),
            'action': 'approve_incident' if approval.approved else 'deny_incident',
            'result': 'approved' if approval.approved else 'denied',
            'feedback': approval.feedback
        }]

        return self._state_to_incident(state)

    def get_pending_incidents(self) -> List[Incident]:
        """Get all pending incidents awaiting approval"""
        return [
            self._state_to_incident(state)
            for state in self.pending_incidents.values()
        ]

    def _state_to_incident(self, state: AgentState) -> Incident:
        """Convert agent state to Incident model"""
        anomaly = state['anomaly']
        if isinstance(anomaly, dict):
            anomaly = AnomalyResult(**anomaly)

        return Incident(
            id=state.get('incident_id'),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            status=state.get('incident_status', IncidentStatus.DETECTED),
            anomaly=anomaly,
            classification=state.get('threat_classification'),
            recommended_actions=state.get('recommended_actions', []),
            selected_action=state.get('selected_action'),
            decision_reasoning=state.get('decision_reasoning'),
            agent_logs=state.get('agent_logs', []),
            human_feedback=state.get('human_feedback'),
            execution_result=state.get('execution_result')
        )


# Singleton instance
soc_workflow = SOCWorkflow()


def process_anomaly(
    anomaly: AnomalyResult,
    raw_logs: List[Dict[str, Any]],
    tenant_context: Optional[Dict[str, Any]] = None
) -> Incident:
    """Convenience function to process an anomaly"""
    return soc_workflow.process_anomaly(anomaly, raw_logs, tenant_context)


def approve_incident(approval: IncidentApproval) -> Incident:
    """Convenience function to approve an incident"""
    return soc_workflow.approve_incident(approval)


def get_pending_incidents() -> List[Incident]:
    """Convenience function to get pending incidents"""
    return soc_workflow.get_pending_incidents()
