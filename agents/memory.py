"""
Agent Memory and Learning System
Provides long-term memory and learning from past decisions
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import json

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from backend.utils import utc_isoformat

from config.settings import settings


class AgentMemory:
    """
    Long-term memory system for agents that enables learning from past decisions.
    Stores outcomes, tracks accuracy, and provides context for future decisions.
    Supports multi-tenancy with organization-scoped learning.
    """

    def __init__(self):
        # Global state (for backwards compatibility)
        self.decisions: List[Dict[str, Any]] = []
        self.outcomes: Dict[str, Dict[str, Any]] = {}  # decision_id -> outcome
        self.attack_patterns: Dict[str, List[Dict]] = defaultdict(list)
        self.ip_reputation: Dict[str, Dict[str, Any]] = {}
        self.action_effectiveness: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"success": 0, "failure": 0, "total": 0}
        )
        self.learned_thresholds: Dict[str, float] = {
            "auth_failure_threshold": 10,
            "burst_rate_threshold": 10,
            "confidence_auto_approve": 0.75,
            "min_samples_for_learning": 10,
        }
        self.false_positives: List[Dict] = []
        self.false_negatives: List[Dict] = []

        # Tenant-scoped state
        self._org_decisions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._org_outcomes: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self._org_ip_reputation: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self._org_action_effectiveness: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: {"success": 0, "failure": 0, "total": 0})
        )
        self._org_learned_thresholds: Dict[str, Dict[str, float]] = {}
        self._org_false_positives: Dict[str, List[Dict]] = defaultdict(list)
        self._org_false_negatives: Dict[str, List[Dict]] = defaultdict(list)

    def _get_org_thresholds(self, org_id: str) -> Dict[str, float]:
        """Get or create thresholds for an organization"""
        if org_id not in self._org_learned_thresholds:
            self._org_learned_thresholds[org_id] = {
                "auth_failure_threshold": 10,
                "burst_rate_threshold": 10,
                "confidence_auto_approve": 0.75,
                "min_samples_for_learning": 10,
            }
        return self._org_learned_thresholds[org_id]

    def store_decision(
        self,
        decision_id: str,
        attack_type: str,
        severity: str,
        confidence: float,
        action_taken: str,
        source_ips: List[str],
        features: Dict[str, Any],
        reasoning: str,
        auto_approved: bool,
        org_id: Optional[str] = None,
    ) -> None:
        """Store a decision for future learning"""
        decision = {
            "id": decision_id,
            "timestamp": utc_isoformat(),
            "attack_type": attack_type,
            "severity": severity,
            "confidence": confidence,
            "action_taken": action_taken,
            "source_ips": source_ips,
            "features": features,
            "reasoning": reasoning,
            "auto_approved": auto_approved,
            "outcome": None,  # To be updated later
            "org_id": org_id,
        }
        self.decisions.append(decision)

        # Also store in org-specific list
        if org_id:
            self._org_decisions[org_id].append(decision)

        # Update IP reputation (both global and org-specific)
        for ip in source_ips:
            # Global reputation
            if ip not in self.ip_reputation:
                self.ip_reputation[ip] = {
                    "first_seen": utc_isoformat(),
                    "incident_count": 0,
                    "attack_types": [],
                    "risk_score": 0.5,
                }
            self.ip_reputation[ip]["incident_count"] += 1
            self.ip_reputation[ip]["attack_types"].append(attack_type)
            self.ip_reputation[ip]["last_seen"] = utc_isoformat()
            self.ip_reputation[ip]["risk_score"] = min(
                1.0, self.ip_reputation[ip]["risk_score"] + 0.1
            )

            # Org-specific reputation
            if org_id:
                if ip not in self._org_ip_reputation[org_id]:
                    self._org_ip_reputation[org_id][ip] = {
                        "first_seen": utc_isoformat(),
                        "incident_count": 0,
                        "attack_types": [],
                        "risk_score": 0.5,
                    }
                self._org_ip_reputation[org_id][ip]["incident_count"] += 1
                self._org_ip_reputation[org_id][ip]["attack_types"].append(attack_type)
                self._org_ip_reputation[org_id][ip]["last_seen"] = utc_isoformat()
                self._org_ip_reputation[org_id][ip]["risk_score"] = min(
                    1.0, self._org_ip_reputation[org_id][ip]["risk_score"] + 0.1
                )

        # Store attack pattern
        self.attack_patterns[attack_type].append({
            "features": features,
            "confidence": confidence,
            "timestamp": utc_isoformat(),
        })

    def record_outcome(
        self,
        decision_id: str,
        success: bool,
        feedback: Optional[str] = None,
        was_false_positive: bool = False,
        was_false_negative: bool = False,
    ) -> None:
        """Record the outcome of a decision for learning"""
        outcome = {
            "decision_id": decision_id,
            "success": success,
            "feedback": feedback,
            "was_false_positive": was_false_positive,
            "was_false_negative": was_false_negative,
            "recorded_at": utc_isoformat(),
        }
        self.outcomes[decision_id] = outcome

        # Find the decision and update it
        for decision in self.decisions:
            if decision["id"] == decision_id:
                decision["outcome"] = outcome
                action = decision["action_taken"]

                # Update action effectiveness
                self.action_effectiveness[action]["total"] += 1
                if success:
                    self.action_effectiveness[action]["success"] += 1
                else:
                    self.action_effectiveness[action]["failure"] += 1

                # Track false positives/negatives for learning
                if was_false_positive:
                    self.false_positives.append(decision)
                    self._adjust_thresholds_for_false_positive(decision)
                if was_false_negative:
                    self.false_negatives.append(decision)
                    self._adjust_thresholds_for_false_negative(decision)

                break

    def _adjust_thresholds_for_false_positive(self, decision: Dict) -> None:
        """Adjust thresholds when we detect a false positive (over-reaction)"""
        # Increase thresholds slightly to be less sensitive
        features = decision.get("features", {})
        if features.get("auth_failures", 0) > 0:
            current = self.learned_thresholds["auth_failure_threshold"]
            self.learned_thresholds["auth_failure_threshold"] = min(20, current + 1)

        # Slightly lower auto-approve confidence requirement
        current_conf = self.learned_thresholds["confidence_auto_approve"]
        self.learned_thresholds["confidence_auto_approve"] = min(0.9, current_conf + 0.02)

    def _adjust_thresholds_for_false_negative(self, decision: Dict) -> None:
        """Adjust thresholds when we miss a real attack (under-reaction)"""
        # Decrease thresholds to be more sensitive
        features = decision.get("features", {})
        if features.get("auth_failures", 0) > 0:
            current = self.learned_thresholds["auth_failure_threshold"]
            self.learned_thresholds["auth_failure_threshold"] = max(3, current - 1)

        # Lower auto-approve confidence requirement to catch more
        current_conf = self.learned_thresholds["confidence_auto_approve"]
        self.learned_thresholds["confidence_auto_approve"] = max(0.6, current_conf - 0.02)

    def get_ip_reputation(self, ip: str) -> Dict[str, Any]:
        """Get reputation data for an IP"""
        if ip in self.ip_reputation:
            return self.ip_reputation[ip]
        return {
            "first_seen": None,
            "incident_count": 0,
            "attack_types": [],
            "risk_score": 0.5,  # Neutral for unknown
        }

    def get_similar_incidents(
        self, attack_type: str, features: Dict[str, Any], limit: int = 5
    ) -> List[Dict]:
        """Find similar past incidents for context"""
        similar = []
        for decision in reversed(self.decisions):  # Most recent first
            if decision["attack_type"] == attack_type and decision.get("outcome"):
                similar.append(decision)
                if len(similar) >= limit:
                    break
        return similar

    def get_action_success_rate(self, action_type: str) -> float:
        """Get historical success rate for an action type"""
        stats = self.action_effectiveness[action_type]
        if stats["total"] == 0:
            return 0.8  # Default assumption for new actions
        return stats["success"] / stats["total"]

    def get_recommended_action(
        self, attack_type: str, severity: str
    ) -> Tuple[str, float]:
        """Get recommended action based on historical effectiveness"""
        # Get all actions used for this attack type
        action_scores = defaultdict(list)
        for decision in self.decisions:
            if decision["attack_type"] == attack_type:
                if decision.get("outcome", {}).get("success"):
                    action_scores[decision["action_taken"]].append(1.0)
                elif decision.get("outcome"):
                    action_scores[decision["action_taken"]].append(0.0)

        if not action_scores:
            # No historical data, return default based on severity
            defaults = {
                "CRITICAL": ("BLOCK_IP", 0.7),
                "HIGH": ("BLOCK_IP", 0.7),
                "MEDIUM": ("RATE_LIMIT", 0.7),
                "LOW": ("MONITOR", 0.7),
            }
            return defaults.get(severity, ("ALERT", 0.6))

        # Find best performing action
        best_action = None
        best_score = 0.0
        for action, scores in action_scores.items():
            avg_score = sum(scores) / len(scores)
            if avg_score > best_score:
                best_score = avg_score
                best_action = action

        return (best_action, best_score)

    def should_auto_approve(self, confidence: float, severity: str) -> Tuple[bool, str]:
        """Determine if an action should be auto-approved based on learning"""
        threshold = self.learned_thresholds["confidence_auto_approve"]

        # Always require human review for critical severity with low confidence
        if severity == "CRITICAL" and confidence < 0.85:
            return False, f"Critical severity with confidence {confidence:.2f} < 0.85 requires review"

        # Auto-approve if confidence exceeds learned threshold
        if confidence >= threshold:
            return True, f"Confidence {confidence:.2f} >= threshold {threshold:.2f}"

        # Check historical accuracy for similar decisions
        recent_accuracy = self._get_recent_accuracy()
        if recent_accuracy > 0.9 and confidence >= 0.7:
            return True, f"High recent accuracy ({recent_accuracy:.2f}) allows lower threshold"

        return False, f"Confidence {confidence:.2f} < threshold {threshold:.2f}"

    def _get_recent_accuracy(self, window_hours: int = 24) -> float:
        """Get accuracy of recent decisions"""
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        recent = [
            d for d in self.decisions
            if d.get("outcome") and datetime.fromisoformat(d["timestamp"]) > cutoff
        ]
        if len(recent) < 5:
            return 0.8  # Not enough data, assume decent accuracy

        correct = sum(1 for d in recent if d["outcome"].get("success"))
        return correct / len(recent)

    def get_learning_stats(self) -> Dict[str, Any]:
        """Get statistics about the learning system"""
        total_decisions = len(self.decisions)
        decisions_with_outcomes = len([d for d in self.decisions if d.get("outcome")])

        return {
            "total_decisions": total_decisions,
            "decisions_with_feedback": decisions_with_outcomes,
            "false_positives": len(self.false_positives),
            "false_negatives": len(self.false_negatives),
            "learned_thresholds": self.learned_thresholds,
            "action_effectiveness": dict(self.action_effectiveness),
            "known_ips": len(self.ip_reputation),
            "recent_accuracy": self._get_recent_accuracy(),
            "auto_approve_threshold": self.learned_thresholds["confidence_auto_approve"],
        }

    def get_context_for_decision(
        self, attack_type: str, source_ips: List[str], features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get all relevant context for making a decision"""
        # Get IP reputations
        ip_reputations = {ip: self.get_ip_reputation(ip) for ip in source_ips}

        # Get similar past incidents
        similar_incidents = self.get_similar_incidents(attack_type, features)

        # Get recommended action based on history
        recommended_action, action_confidence = self.get_recommended_action(
            attack_type, features.get("severity", "MEDIUM")
        )

        # Get learned thresholds
        thresholds = self.learned_thresholds.copy()

        return {
            "ip_reputations": ip_reputations,
            "similar_incidents": [
                {
                    "attack_type": i["attack_type"],
                    "action_taken": i["action_taken"],
                    "success": i.get("outcome", {}).get("success"),
                    "confidence": i["confidence"],
                }
                for i in similar_incidents
            ],
            "recommended_action": recommended_action,
            "action_confidence": action_confidence,
            "learned_thresholds": thresholds,
            "recent_accuracy": self._get_recent_accuracy(),
        }

    # ============= Tenant-aware methods =============

    def get_ip_reputation_for_org(self, org_id: str, ip: str) -> Dict[str, Any]:
        """Get reputation data for an IP within an organization"""
        if org_id in self._org_ip_reputation and ip in self._org_ip_reputation[org_id]:
            return self._org_ip_reputation[org_id][ip]
        return {
            "first_seen": None,
            "incident_count": 0,
            "attack_types": [],
            "risk_score": 0.5,
        }

    def get_learning_stats_for_org(self, org_id: str) -> Dict[str, Any]:
        """Get statistics about the learning system for an organization"""
        org_decisions = self._org_decisions.get(org_id, [])
        decisions_with_outcomes = len([d for d in org_decisions if d.get("outcome")])

        return {
            "total_decisions": len(org_decisions),
            "decisions_with_feedback": decisions_with_outcomes,
            "false_positives": len(self._org_false_positives.get(org_id, [])),
            "false_negatives": len(self._org_false_negatives.get(org_id, [])),
            "learned_thresholds": self._get_org_thresholds(org_id),
            "action_effectiveness": dict(self._org_action_effectiveness.get(org_id, {})),
            "known_ips": len(self._org_ip_reputation.get(org_id, {})),
            "recent_accuracy": self._get_recent_accuracy_for_org(org_id),
            "auto_approve_threshold": self._get_org_thresholds(org_id).get("confidence_auto_approve", 0.75),
        }

    def _get_recent_accuracy_for_org(self, org_id: str, window_hours: int = 24) -> float:
        """Get accuracy of recent decisions for an organization"""
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        org_decisions = self._org_decisions.get(org_id, [])

        recent = [
            d for d in org_decisions
            if d.get("outcome") and datetime.fromisoformat(d["timestamp"]) > cutoff
        ]
        if len(recent) < 5:
            return 0.8

        correct = sum(1 for d in recent if d["outcome"].get("success"))
        return correct / len(recent)

    def get_similar_incidents_for_org(
        self, org_id: str, attack_type: str, features: Dict[str, Any], limit: int = 5
    ) -> List[Dict]:
        """Find similar past incidents for an organization"""
        org_decisions = self._org_decisions.get(org_id, [])
        similar = []
        for decision in reversed(org_decisions):
            if decision["attack_type"] == attack_type and decision.get("outcome"):
                similar.append(decision)
                if len(similar) >= limit:
                    break
        return similar


# Singleton instance
agent_memory = AgentMemory()
