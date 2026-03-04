"""
Autonomous Decision Agent
Uses LLM as PRIMARY reasoning engine with learning from past decisions.
No hardcoded playbooks - LLM reasons about best actions.
"""
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import json

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from backend.utils import utc_isoformat

from config.settings import settings
from agents.agent_state import AgentState
from agents.memory import agent_memory
from backend.models.schemas import (
    ThreatClassification, RecommendedAction, ActionType,
    AttackType, SeverityLevel, IncidentStatus
)


class AutonomousDecisionAgent:
    """
    Truly autonomous decision agent that:
    1. Uses LLM as primary reasoning engine
    2. Learns from past decisions and outcomes
    3. Auto-approves high-confidence decisions
    4. Only escalates genuinely uncertain cases
    """

    def __init__(self):
        self.groq_client = None
        self._init_groq()
        self.decision_count = 0
        self.auto_approved_count = 0

    def _init_groq(self):
        """Initialize Groq client - REQUIRED for autonomous operation"""
        try:
            from groq import Groq
            if settings.GROQ_API_KEY:
                self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
                print("[DecisionAgent] Groq initialized - autonomous mode enabled")
            else:
                print("[DecisionAgent] WARNING: No GROQ_API_KEY - falling back to rules")
        except ImportError:
            print("[DecisionAgent] WARNING: Groq not installed")
        except Exception as e:
            print(f"[DecisionAgent] Error initializing Groq: {e}")

    def decide(self, state: AgentState) -> AgentState:
        """Make autonomous decision with learning context"""
        start_time = datetime.utcnow()
        self.decision_count += 1

        classification = state.get('threat_classification')
        log_analysis = state.get('log_analysis', {})
        anomaly = state['anomaly']

        # Get source IPs
        source_ips = []
        if hasattr(anomaly, 'source_ips'):
            source_ips = anomaly.source_ips
        elif isinstance(anomaly, dict):
            source_ips = anomaly.get('source_ips', [])

        # Get learning context from memory
        learning_context = agent_memory.get_context_for_decision(
            attack_type=classification.attack_type.value if classification else "UNKNOWN",
            source_ips=source_ips,
            features=log_analysis.get('metrics', {})
        )

        # Make decision using LLM with full context
        if self.groq_client and classification:
            actions, reasoning, confidence = self._autonomous_decision(
                classification, log_analysis, anomaly, learning_context
            )
        else:
            actions, reasoning, confidence = self._fallback_decision(
                classification, log_analysis, anomaly
            )

        selected_action = actions[0] if actions else None

        # Determine if auto-approve based on learned thresholds
        auto_approve, approval_reason = self._should_auto_execute(
            classification, selected_action, confidence, learning_context
        )

        if auto_approve:
            self.auto_approved_count += 1
            state['incident_status'] = IncidentStatus.APPROVED
            state['requires_human_approval'] = False
            reasoning += f"\n\n[AUTO-APPROVED: {approval_reason}]"
        else:
            state['incident_status'] = IncidentStatus.PENDING_APPROVAL
            state['requires_human_approval'] = True
            reasoning += f"\n\n[REQUIRES REVIEW: {approval_reason}]"

        state['recommended_actions'] = actions
        state['selected_action'] = selected_action
        state['decision_reasoning'] = reasoning

        # Store decision in memory for learning
        if selected_action and classification:
            decision_id = f"DEC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{self.decision_count}"
            agent_memory.store_decision(
                decision_id=decision_id,
                attack_type=classification.attack_type.value,
                severity=classification.severity.value,
                confidence=confidence,
                action_taken=selected_action.action_type.value,
                source_ips=source_ips[:5],
                features=log_analysis.get('metrics', {}),
                reasoning=reasoning,
                auto_approved=auto_approve
            )

        state['agent_logs'] = [{
            'agent': 'AutonomousDecisionAgent',
            'timestamp': utc_isoformat(),
            'duration_ms': (datetime.utcnow() - start_time).total_seconds() * 1000,
            'action': 'autonomous_decision',
            'result': 'auto_approved' if auto_approve else 'pending_review',
            'selected_action': selected_action.action_type.value if selected_action else None,
            'confidence': confidence,
            'reasoning': reasoning[:500] if reasoning else None,  # Include decision reasoning in logs
            'learning_context': {
                'similar_incidents': len(learning_context.get('similar_incidents', [])),
                'known_ips': len([ip for ip in source_ips if agent_memory.get_ip_reputation(ip).get('incident_count', 0) > 0]),
                'recent_accuracy': learning_context.get('recent_accuracy', 0),
            },
            'auto_approve_reason': approval_reason,
            'total_decisions': self.decision_count,
            'auto_approved_total': self.auto_approved_count,
        }]

        return state

    def _should_auto_execute(
        self,
        classification: ThreatClassification,
        action: RecommendedAction,
        confidence: float,
        learning_context: Dict
    ) -> Tuple[bool, str]:
        """
        Determine if action should be auto-executed based on:
        1. Confidence level
        2. Historical accuracy
        3. Severity and action type
        4. Learned thresholds
        """
        if not classification or not action:
            return False, "Missing classification or action"

        # Get learned auto-approve threshold
        threshold = learning_context.get('learned_thresholds', {}).get(
            'confidence_auto_approve', 0.75
        )

        # High confidence = auto-approve
        if confidence >= 0.85:
            return True, f"High confidence ({confidence:.0%} >= 85%)"

        # Check historical accuracy
        recent_accuracy = learning_context.get('recent_accuracy', 0.8)
        if recent_accuracy >= 0.9 and confidence >= 0.7:
            return True, f"Excellent recent accuracy ({recent_accuracy:.0%}) with good confidence"

        # For non-critical actions, be more permissive
        safe_actions = [ActionType.MONITOR, ActionType.ALERT, ActionType.RATE_LIMIT]
        if action.action_type in safe_actions and confidence >= 0.7:
            return True, f"Safe action type ({action.action_type.value}) with adequate confidence"

        # For known malicious IPs (repeat offenders), auto-approve blocks
        similar = learning_context.get('similar_incidents', [])
        if similar and all(i.get('success') for i in similar[:3]):
            return True, f"Similar past incidents all successful"

        # Default: require review for uncertain cases
        if confidence < threshold:
            return False, f"Confidence ({confidence:.0%}) below threshold ({threshold:.0%})"

        if classification.severity == SeverityLevel.CRITICAL and confidence < 0.9:
            return False, f"Critical severity requires high confidence"

        # If we get here with decent confidence, auto-approve
        if confidence >= threshold:
            return True, f"Confidence meets learned threshold ({threshold:.0%})"

        return False, "Default to human review for safety"

    def _autonomous_decision(
        self,
        classification: ThreatClassification,
        analysis: Dict,
        anomaly,
        learning_context: Dict
    ) -> Tuple[List[RecommendedAction], str, float]:
        """
        Use LLM for autonomous decision-making with full learning context.
        This is the PRIMARY decision path - not a fallback.
        """
        source_ips = []
        if hasattr(anomaly, 'source_ips'):
            source_ips = anomaly.source_ips
        elif isinstance(anomaly, dict):
            source_ips = anomaly.get('source_ips', [])

        # Build rich context for LLM
        ip_context = []
        for ip in source_ips[:3]:
            rep = learning_context.get('ip_reputations', {}).get(ip, {})
            if rep.get('incident_count', 0) > 0:
                ip_context.append(f"- {ip}: {rep['incident_count']} previous incidents, risk score {rep.get('risk_score', 0.5):.2f}")
            else:
                ip_context.append(f"- {ip}: First time seen")

        similar_context = []
        for incident in learning_context.get('similar_incidents', [])[:3]:
            similar_context.append(
                f"- {incident['attack_type']}: {incident['action_taken']} -> {'SUCCESS' if incident.get('success') else 'FAILED'}"
            )

        prompt = f"""You are an autonomous SOC decision engine. Make a decision on how to respond to this threat.

## CURRENT THREAT
- Attack Type: {classification.attack_type.value}
- Severity: {classification.severity.value}
- Detection Confidence: {classification.confidence:.0%}
- Key Indicators: {', '.join(classification.indicators[:5])}
- MITRE Techniques: {', '.join(classification.mitre_techniques[:3])}

## METRICS
- Authentication Failures: {analysis.get('auth_failures', 0)}
- Request Burst Rate: {analysis.get('metrics', {}).get('burst_rate', 0)}
- Error Rate: {analysis.get('metrics', {}).get('error_rate', 0)}
- Unique Paths Ratio: {analysis.get('metrics', {}).get('unique_paths_ratio', 0)}

## SOURCE IPs REPUTATION
{chr(10).join(ip_context) if ip_context else "No previous data on these IPs"}

## LEARNING FROM PAST DECISIONS
Similar incidents and their outcomes:
{chr(10).join(similar_context) if similar_context else "No similar past incidents"}

Historical recommended action for {classification.attack_type.value}: {learning_context.get('recommended_action', 'None')}
Action historical success rate: {learning_context.get('action_confidence', 0):.0%}
Recent overall accuracy: {learning_context.get('recent_accuracy', 0.8):.0%}

## YOUR TASK
Based on the threat data AND learning from past decisions:
1. Decide the best response action(s)
2. Provide clear reasoning
3. Set your confidence level (0.0-1.0)

Available actions:
- BLOCK_IP: Block the source IP (use for confirmed attacks)
- RATE_LIMIT: Throttle requests (use for potential attacks)
- ALERT: Send alert to SOC team (always include)
- ESCALATE: Escalate to incident response (critical only)
- MONITOR: Enhanced monitoring (low confidence situations)

Respond with JSON only:
{{
    "reasoning": "Your detailed reasoning about why this action is appropriate given the threat AND learning context",
    "confidence": 0.0-1.0,
    "primary_action": {{
        "action_type": "BLOCK_IP|RATE_LIMIT|ALERT|ESCALATE|MONITOR",
        "target": "{source_ips[0] if source_ips else 'unknown'}",
        "parameters": {{"duration_hours": 24, "reason": "brief reason"}}
    }},
    "secondary_actions": [
        {{
            "action_type": "ALERT",
            "target": "soc-team",
            "parameters": {{"priority": "high|medium|low"}}
        }}
    ]
}}"""

        try:
            response = self.groq_client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an autonomous security decision engine. Be decisive and confident. Learn from past outcomes to improve decisions. Always respond with valid JSON only, no markdown or explanation."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1000
            )

            content = response.choices[0].message.content

            # Handle empty response
            if not content or not content.strip():
                print("[DecisionAgent] Empty LLM response, using fallback")
                return self._fallback_decision(classification, analysis, anomaly)

            content = content.strip()

            # Parse JSON response - try multiple extraction methods
            result = self._parse_llm_json(content)
            if result is None:
                print("[DecisionAgent] Could not parse LLM JSON, using fallback")
                return self._fallback_decision(classification, analysis, anomaly)

            actions = []
            reasoning = result.get('reasoning', 'LLM decision')
            confidence = float(result.get('confidence', classification.confidence))

            # Parse primary action
            primary = result.get('primary_action', {})
            if primary:
                action = RecommendedAction(
                    action_type=ActionType(primary.get('action_type', 'MONITOR')),
                    target=primary.get('target', source_ips[0] if source_ips else 'unknown'),
                    parameters=primary.get('parameters', {}),
                    reasoning=reasoning,
                    confidence=confidence
                )
                actions.append(action)

            # Parse secondary actions
            for sec in result.get('secondary_actions', []):
                action = RecommendedAction(
                    action_type=ActionType(sec.get('action_type', 'ALERT')),
                    target=sec.get('target', 'soc-team'),
                    parameters=sec.get('parameters', {}),
                    reasoning=f"Secondary: {sec.get('action_type')}",
                    confidence=confidence * 0.9
                )
                actions.append(action)

            if not actions:
                return self._fallback_decision(classification, analysis, anomaly)

            return actions, reasoning, confidence

        except json.JSONDecodeError as e:
            print(f"[DecisionAgent] JSON parse error: {e}")
            return self._fallback_decision(classification, analysis, anomaly)
        except Exception as e:
            print(f"[DecisionAgent] LLM error: {e}")
            return self._fallback_decision(classification, analysis, anomaly)

    def _parse_llm_json(self, content: str) -> Optional[Dict]:
        """Parse JSON from LLM response, handling various formats and truncation."""
        import re

        # Method 1: Direct parse
        try:
            if content.startswith('{'):
                return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Method 2: Extract from markdown code block
        try:
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0].strip()
                return json.loads(json_str)
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0].strip()
                return json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            pass

        # Method 3: Find JSON object in response
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        # Method 4: Try to fix truncated JSON
        try:
            start = content.find('{')
            if start >= 0:
                json_str = content[start:]
                # Count braces to detect truncation
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                if open_braces > close_braces:
                    # Add missing closing braces
                    json_str += '}' * (open_braces - close_braces)
                # Try to fix unterminated strings by adding quote
                if json_str.count('"') % 2 != 0:
                    json_str += '"'
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Method 5: Extract just the key fields we need using regex
        try:
            result = {}
            # Extract action_type
            action_match = re.search(r'"action_type"\s*:\s*"([^"]+)"', content)
            if action_match:
                result['primary_action'] = {'action_type': action_match.group(1)}
            # Extract reasoning
            reason_match = re.search(r'"reasoning"\s*:\s*"([^"]*)', content)
            if reason_match:
                result['reasoning'] = reason_match.group(1)
            # Extract confidence
            conf_match = re.search(r'"confidence"\s*:\s*([\d.]+)', content)
            if conf_match:
                result['confidence'] = float(conf_match.group(1))
            # Extract target
            target_match = re.search(r'"target"\s*:\s*"([^"]+)"', content)
            if target_match and 'primary_action' in result:
                result['primary_action']['target'] = target_match.group(1)

            if result.get('primary_action'):
                return result
        except Exception:
            pass

        return None

    def _fallback_decision(
        self,
        classification: ThreatClassification,
        analysis: Dict,
        anomaly
    ) -> Tuple[List[RecommendedAction], str, float]:
        """
        Fallback decision when LLM unavailable.
        Uses learned thresholds instead of hardcoded values.
        """
        source_ips = []
        if hasattr(anomaly, 'source_ips'):
            source_ips = anomaly.source_ips
        elif isinstance(anomaly, dict):
            source_ips = anomaly.get('source_ips', [])

        target_ip = source_ips[0] if source_ips else "unknown"
        actions = []

        if not classification:
            return self._default_actions(target_ip), "No classification, defaulting to monitoring", 0.5

        # Get recommended action from memory
        recommended, rec_confidence = agent_memory.get_recommended_action(
            classification.attack_type.value,
            classification.severity.value
        )

        # Create primary action based on recommendation
        action_type = ActionType(recommended) if recommended else ActionType.MONITOR
        confidence = max(classification.confidence, rec_confidence)

        actions.append(RecommendedAction(
            action_type=action_type,
            target=target_ip,
            parameters=self._get_action_params(action_type, classification),
            reasoning=f"Based on historical effectiveness for {classification.attack_type.value}",
            confidence=confidence
        ))

        # Always add alert
        actions.append(RecommendedAction(
            action_type=ActionType.ALERT,
            target="soc-team",
            parameters={'priority': classification.severity.value.lower()},
            reasoning="Alert SOC team",
            confidence=confidence
        ))

        reasoning = (
            f"Fallback decision for {classification.attack_type.value} "
            f"({classification.severity.value}). Using learned recommendation: {recommended}"
        )

        return actions, reasoning, confidence

    def _get_action_params(self, action_type: ActionType, classification: ThreatClassification) -> Dict:
        """Get appropriate parameters for action type"""
        if action_type == ActionType.BLOCK_IP:
            return {
                'duration_hours': 24 if classification.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL] else 6,
                'permanent': classification.severity == SeverityLevel.CRITICAL
            }
        elif action_type == ActionType.RATE_LIMIT:
            return {
                'requests_per_minute': 10 if classification.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL] else 30,
                'duration_minutes': 60
            }
        elif action_type == ActionType.MONITOR:
            return {
                'duration_minutes': 120,
                'detailed_logging': True
            }
        return {}

    def _default_actions(self, target_ip: str) -> List[RecommendedAction]:
        """Default actions when no classification available"""
        return [
            RecommendedAction(
                action_type=ActionType.MONITOR,
                target=target_ip,
                parameters={'duration_minutes': 60},
                reasoning="Unknown threat, initiating monitoring",
                confidence=0.5
            ),
            RecommendedAction(
                action_type=ActionType.ALERT,
                target="soc-team",
                parameters={'priority': 'medium'},
                reasoning="Alert for investigation",
                confidence=0.5
            )
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get decision agent statistics"""
        return {
            "total_decisions": self.decision_count,
            "auto_approved": self.auto_approved_count,
            "auto_approve_rate": self.auto_approved_count / max(1, self.decision_count),
            "learning_stats": agent_memory.get_learning_stats()
        }


# Singleton instance
decision_agent = AutonomousDecisionAgent()
