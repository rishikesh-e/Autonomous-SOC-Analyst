"""
Autonomous Response Agent - Executes defensive actions and records outcomes for learning
Supports multi-tenancy with organization-scoped actions
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from backend.utils import utc_isoformat

from config.settings import settings
from agents.agent_state import AgentState
from agents.memory import agent_memory
from backend.models.schemas import (
    RecommendedAction, ActionType, IncidentStatus
)


class ResponseAgent:
    """
    Agent 4: Response Agent
    Responsibilities:
    - Execute approved defensive actions
    - Simulate IP blocking, rate limiting
    - Send alerts and escalations
    - Track execution results
    - Support multi-tenancy with org-scoped actions
    """

    def __init__(self):
        # Tenant-scoped state: Dict[org_id, Dict[ip, info]]
        self.blocked_ips: Dict[str, Dict[str, Dict]] = {}
        self.rate_limited_ips: Dict[str, Dict[str, Dict]] = {}
        self.alerts_sent: Dict[str, List[Dict]] = {}
        self.escalations: Dict[str, List[Dict]] = {}
        self.monitored_ips: Dict[str, Dict[str, Dict]] = {}

        # Global fallback for backwards compatibility
        self._global_blocked_ips: Dict[str, Dict] = {}
        self._global_rate_limited_ips: Dict[str, Dict] = {}
        self._global_alerts_sent: List[Dict] = []
        self._global_escalations: List[Dict] = []
        self._global_monitored_ips: Dict[str, Dict] = {}

    def _get_org_id(self, state: AgentState) -> Optional[str]:
        """Extract org_id from state's tenant context"""
        tenant_context = state.get('tenant_context')
        if tenant_context:
            return tenant_context.get('org_id')
        return None

    def _ensure_org_state(self, org_id: str) -> None:
        """Ensure state dictionaries exist for an organization"""
        if org_id not in self.blocked_ips:
            self.blocked_ips[org_id] = {}
        if org_id not in self.rate_limited_ips:
            self.rate_limited_ips[org_id] = {}
        if org_id not in self.alerts_sent:
            self.alerts_sent[org_id] = []
        if org_id not in self.escalations:
            self.escalations[org_id] = []
        if org_id not in self.monitored_ips:
            self.monitored_ips[org_id] = {}

    def execute(self, state: AgentState) -> AgentState:
        """
        Execute the action - autonomous mode executes approved actions immediately.
        Records outcomes for learning system.
        """
        start_time = datetime.utcnow()

        selected_action = state.get('selected_action')
        incident_status = state.get('incident_status')
        requires_approval = state.get('requires_human_approval', False)
        org_id = self._get_org_id(state)

        if org_id:
            self._ensure_org_state(org_id)

        # Skip if denied
        if incident_status == IncidentStatus.DENIED:
            self._record_outcome(state, success=False, reason="Human denied")
            state['agent_logs'] = [{
                'agent': 'AutonomousResponseAgent',
                'timestamp': utc_isoformat(),
                'action': 'execute_response',
                'result': 'denied',
                'reason': 'Action was denied'
            }]
            return state

        # If requires approval and still pending, don't execute yet
        if requires_approval and incident_status == IncidentStatus.PENDING_APPROVAL:
            state['agent_logs'] = [{
                'agent': 'AutonomousResponseAgent',
                'timestamp': utc_isoformat(),
                'action': 'execute_response',
                'result': 'awaiting_approval',
                'reason': 'Escalated to human review'
            }]
            return state

        if not selected_action:
            state['agent_logs'] = [{
                'agent': 'AutonomousResponseAgent',
                'timestamp': utc_isoformat(),
                'action': 'execute_response',
                'result': 'skipped',
                'reason': 'No action selected'
            }]
            return state

        # AUTONOMOUS EXECUTION - Execute if approved (including auto-approved)
        execution_result = self._execute_action(selected_action, org_id)

        # Record outcome for learning
        self._record_outcome(state, success=execution_result.get('success', True))

        # Execute all recommended actions, not just the primary
        all_results = [execution_result]
        for action in state.get('recommended_actions', [])[1:]:
            result = self._execute_action(action, org_id)
            all_results.append(result)

        # Update state
        state['execution_result'] = {
            'primary': execution_result,
            'all_actions': all_results,
            'total_executed': len(all_results),
            'auto_executed': not requires_approval,
            'org_id': org_id
        }
        state['incident_status'] = IncidentStatus.EXECUTED if execution_result.get('success') else IncidentStatus.APPROVED

        state['agent_logs'] = [{
            'agent': 'AutonomousResponseAgent',
            'timestamp': utc_isoformat(),
            'duration_ms': (datetime.utcnow() - start_time).total_seconds() * 1000,
            'action': 'autonomous_execution',
            'result': 'success' if execution_result.get('success') else 'failed',
            'auto_executed': not requires_approval,
            'action_type': selected_action.action_type.value,
            'target': selected_action.target,
            'actions_executed': len(all_results),
            'org_id': org_id,
            'details': execution_result
        }]

        return state

    def _record_outcome(self, state: AgentState, success: bool, reason: str = None) -> None:
        """Record outcome in memory for learning"""
        try:
            incident_id = state.get('incident_id')
            if incident_id:
                agent_memory.record_outcome(
                    decision_id=incident_id,
                    success=success,
                    feedback=reason,
                    was_false_positive=False,
                    was_false_negative=False
                )
        except Exception as e:
            print(f"[ResponseAgent] Failed to record outcome: {e}")

    def _execute_action(self, action: RecommendedAction, org_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute a specific action"""
        action_handlers = {
            ActionType.BLOCK_IP: self._block_ip,
            ActionType.RATE_LIMIT: self._rate_limit,
            ActionType.ALERT: self._send_alert,
            ActionType.ESCALATE: self._escalate,
            ActionType.MONITOR: self._enable_monitoring,
            ActionType.NO_ACTION: self._no_action
        }

        handler = action_handlers.get(action.action_type, self._no_action)
        return handler(action, org_id)

    def _block_ip(self, action: RecommendedAction, org_id: Optional[str] = None) -> Dict[str, Any]:
        """Simulate IP blocking"""
        ip = action.target
        params = action.parameters

        block_info = {
            'ip': ip,
            'blocked_at': utc_isoformat(),
            'duration_hours': params.get('duration_hours', 24),
            'permanent': params.get('permanent', False),
            'reason': action.reasoning,
            'org_id': org_id
        }

        if org_id:
            self._ensure_org_state(org_id)
            self.blocked_ips[org_id][ip] = block_info
        else:
            self._global_blocked_ips[ip] = block_info

        return {
            'success': True,
            'action': 'block_ip',
            'message': f"IP {ip} has been blocked",
            'details': block_info,
            'simulated': True
        }

    def _rate_limit(self, action: RecommendedAction, org_id: Optional[str] = None) -> Dict[str, Any]:
        """Simulate rate limiting"""
        ip = action.target
        params = action.parameters

        rate_limit_info = {
            'ip': ip,
            'applied_at': utc_isoformat(),
            'requests_per_minute': params.get('requests_per_minute', 30),
            'duration_minutes': params.get('duration_minutes', 60),
            'reason': action.reasoning,
            'org_id': org_id
        }

        if org_id:
            self._ensure_org_state(org_id)
            self.rate_limited_ips[org_id][ip] = rate_limit_info
        else:
            self._global_rate_limited_ips[ip] = rate_limit_info

        return {
            'success': True,
            'action': 'rate_limit',
            'message': f"Rate limiting applied to IP {ip}",
            'details': rate_limit_info,
            'simulated': True
        }

    def _send_alert(self, action: RecommendedAction, org_id: Optional[str] = None) -> Dict[str, Any]:
        """Simulate sending alerts"""
        params = action.parameters

        alert_info = {
            'target': action.target,
            'sent_at': utc_isoformat(),
            'priority': params.get('priority', 'medium'),
            'channels': params.get('channels', ['slack']),
            'message': action.reasoning,
            'org_id': org_id
        }

        if org_id:
            self._ensure_org_state(org_id)
            self.alerts_sent[org_id].append(alert_info)
        else:
            self._global_alerts_sent.append(alert_info)

        return {
            'success': True,
            'action': 'alert',
            'message': f"Alert sent to {action.target}",
            'details': alert_info,
            'simulated': True
        }

    def _escalate(self, action: RecommendedAction, org_id: Optional[str] = None) -> Dict[str, Any]:
        """Simulate escalation"""
        params = action.parameters

        escalation_info = {
            'target': action.target,
            'escalated_at': utc_isoformat(),
            'urgency': params.get('urgency', 'high'),
            'include_forensics': params.get('include_forensics', False),
            'reason': action.reasoning,
            'org_id': org_id
        }

        if org_id:
            self._ensure_org_state(org_id)
            self.escalations[org_id].append(escalation_info)
        else:
            self._global_escalations.append(escalation_info)

        return {
            'success': True,
            'action': 'escalate',
            'message': f"Incident escalated to {action.target}",
            'details': escalation_info,
            'simulated': True
        }

    def _enable_monitoring(self, action: RecommendedAction, org_id: Optional[str] = None) -> Dict[str, Any]:
        """Simulate enhanced monitoring"""
        ip = action.target
        params = action.parameters

        monitoring_info = {
            'ip': ip,
            'started_at': utc_isoformat(),
            'duration_minutes': params.get('duration_minutes', 120),
            'detailed_logging': params.get('detailed_logging', True),
            'alert_threshold': params.get('alert_threshold', 0.7),
            'reason': action.reasoning,
            'org_id': org_id
        }

        if org_id:
            self._ensure_org_state(org_id)
            self.monitored_ips[org_id][ip] = monitoring_info
        else:
            self._global_monitored_ips[ip] = monitoring_info

        return {
            'success': True,
            'action': 'monitor',
            'message': f"Enhanced monitoring enabled for IP {ip}",
            'details': monitoring_info,
            'simulated': True
        }

    def _no_action(self, action: RecommendedAction, org_id: Optional[str] = None) -> Dict[str, Any]:
        """No action taken"""
        return {
            'success': True,
            'action': 'no_action',
            'message': "No action taken",
            'details': {'reason': action.reasoning},
            'simulated': True
        }

    # ============= Tenant-aware getters =============

    def get_blocked_ips_for_org(self, org_id: str) -> List[Dict]:
        """Get list of currently blocked IPs for an organization"""
        if org_id in self.blocked_ips:
            return list(self.blocked_ips[org_id].values())
        return []

    def get_rate_limited_ips_for_org(self, org_id: str) -> List[Dict]:
        """Get list of rate limited IPs for an organization"""
        if org_id in self.rate_limited_ips:
            return list(self.rate_limited_ips[org_id].values())
        return []

    def get_recent_alerts_for_org(self, org_id: str, limit: int = 10) -> List[Dict]:
        """Get recent alerts for an organization"""
        if org_id in self.alerts_sent:
            return self.alerts_sent[org_id][-limit:]
        return []

    def get_active_escalations_for_org(self, org_id: str) -> List[Dict]:
        """Get active escalations for an organization"""
        if org_id in self.escalations:
            return self.escalations[org_id]
        return []

    def unblock_ip_for_org(self, org_id: str, ip: str) -> bool:
        """Remove IP from blocked list for an organization"""
        if org_id in self.blocked_ips and ip in self.blocked_ips[org_id]:
            del self.blocked_ips[org_id][ip]
            return True
        return False

    def remove_rate_limit_for_org(self, org_id: str, ip: str) -> bool:
        """Remove rate limit from IP for an organization"""
        if org_id in self.rate_limited_ips and ip in self.rate_limited_ips[org_id]:
            del self.rate_limited_ips[org_id][ip]
            return True
        return False

    # ============= Legacy methods for backwards compatibility =============

    def get_blocked_ips(self) -> List[Dict]:
        """Get list of currently blocked IPs (legacy, global)"""
        return list(self._global_blocked_ips.values())

    def get_rate_limited_ips(self) -> List[Dict]:
        """Get list of rate limited IPs (legacy, global)"""
        return list(self._global_rate_limited_ips.values())

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Get recent alerts (legacy, global)"""
        return self._global_alerts_sent[-limit:]

    def get_active_escalations(self) -> List[Dict]:
        """Get active escalations (legacy, global)"""
        return self._global_escalations

    def unblock_ip(self, ip: str) -> bool:
        """Remove IP from blocked list (legacy, global)"""
        if ip in self._global_blocked_ips:
            del self._global_blocked_ips[ip]
            return True
        return False

    def remove_rate_limit(self, ip: str) -> bool:
        """Remove rate limit from IP (legacy, global)"""
        if ip in self._global_rate_limited_ips:
            del self._global_rate_limited_ips[ip]
            return True
        return False


# Singleton instance
response_agent = ResponseAgent()
