"""
Threat Classification Agent - Classifies threats based on analysis
"""
from typing import Dict, Any, List
from datetime import datetime
import json

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from backend.utils import utc_isoformat

from config.settings import settings
from agents.agent_state import AgentState
from backend.models.schemas import (
    ThreatClassification, AttackType, SeverityLevel, IncidentStatus
)


# MITRE ATT&CK mappings
MITRE_MAPPINGS = {
    AttackType.BRUTE_FORCE: ["T1110", "T1110.001", "T1110.003"],  # Brute Force techniques
    AttackType.RECONNAISSANCE: ["T1595", "T1592", "T1590"],  # Reconnaissance
    AttackType.DDOS: ["T1498", "T1499"],  # Network DoS
    AttackType.INJECTION: ["T1190", "T1059"],  # Exploit Public-Facing App, Command Execution
    AttackType.SUSPICIOUS_IP: ["T1090", "T1071"],  # Proxy, Application Layer Protocol
    AttackType.AUTH_FAILURE: ["T1078", "T1110"],  # Valid Accounts, Brute Force
    AttackType.ANOMALOUS_TRAFFIC: ["T1071", "T1095"],  # Application/Non-Application Layer Protocol
}


class ThreatClassificationAgent:
    """
    Agent 2: Threat Classification Agent
    Responsibilities:
    - Classify the type of attack
    - Determine severity level
    - Map to MITRE ATT&CK framework
    - Calculate confidence scores
    """

    def __init__(self):
        self.groq_client = None
        self._init_groq()

    def _init_groq(self):
        """Initialize Groq client"""
        try:
            from groq import Groq
            if settings.GROQ_API_KEY:
                self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
        except ImportError:
            print("Groq not installed, using rule-based classification")
        except Exception as e:
            print(f"Error initializing Groq: {e}")

    def classify(self, state: AgentState) -> AgentState:
        """Classify the threat based on log analysis"""
        start_time = datetime.utcnow()

        log_analysis = state.get('log_analysis', {})
        anomaly = state['anomaly']

        # Perform classification
        if self.groq_client:
            classification = self._llm_classification(log_analysis, anomaly)
        else:
            classification = self._rule_based_classification(log_analysis, anomaly)

        # Update state
        state['threat_classification'] = classification
        state['agent_logs'] = [{
            'agent': 'ThreatClassificationAgent',
            'timestamp': utc_isoformat(),
            'duration_ms': (datetime.utcnow() - start_time).total_seconds() * 1000,
            'action': 'classify_threat',
            'result': 'success',
            'classification': {
                'attack_type': classification.attack_type.value,
                'severity': classification.severity.value,
                'confidence': classification.confidence
            }
        }]

        return state

    def _rule_based_classification(self, analysis: Dict, anomaly) -> ThreatClassification:
        """
        Rule-based threat classification with normalized severity levels.

        Severity Thresholds (balanced distribution):
        - LOW: Minor anomalies, low-confidence detections, first-time events
        - MEDIUM: Moderate concern, repeated patterns, elevated metrics
        - HIGH: Serious threats requiring attention, confirmed attack patterns
        - CRITICAL: Immediate action required, active exploitation, severe impact
        """
        features = anomaly.features if hasattr(anomaly, 'features') else anomaly.get('features', {})
        if hasattr(features, 'model_dump'):
            features = features.model_dump()

        llm_insights = analysis.get('llm_insights', {})
        attack_patterns = llm_insights.get('attack_patterns', [])
        threat_indicators = llm_insights.get('threat_indicators', [])

        indicators = []
        attack_type = AttackType.UNKNOWN
        severity = SeverityLevel.LOW
        confidence = 0.5

        # Check for brute force - with tiered severity
        auth_failures = analysis.get('auth_failures', 0)
        failed_ratio = features.get('failed_login_ratio', 0)
        if auth_failures > 5 or failed_ratio > 0.3:
            attack_type = AttackType.BRUTE_FORCE
            indicators.append(f"Auth failures detected: {auth_failures}")
            indicators.append(f"Failed login ratio: {failed_ratio:.2f}")

            # Tiered severity based on failure count
            if auth_failures > 100 or failed_ratio > 0.8:
                severity = SeverityLevel.CRITICAL
                confidence = 0.90
            elif auth_failures > 50 or failed_ratio > 0.6:
                severity = SeverityLevel.HIGH
                confidence = 0.85
            elif auth_failures > 20 or failed_ratio > 0.4:
                severity = SeverityLevel.MEDIUM
                confidence = 0.75
            else:
                severity = SeverityLevel.LOW
                confidence = 0.65

        # Check for reconnaissance - with tiered severity
        suspicious_paths = analysis.get('suspicious_paths', [])
        unique_paths_ratio = features.get('unique_paths_ratio', 0)
        suspicious_count = len(suspicious_paths)

        if suspicious_count > 0 or unique_paths_ratio > 0.7:
            if attack_type == AttackType.UNKNOWN:
                attack_type = AttackType.RECONNAISSANCE
            indicators.append(f"Suspicious paths accessed: {suspicious_count}")
            indicators.append(f"Unique paths ratio: {unique_paths_ratio:.2f}")

            # Tiered severity based on suspicious path count
            if suspicious_count > 20 or unique_paths_ratio > 0.95:
                severity = max(severity, SeverityLevel.HIGH)
                confidence = max(confidence, 0.80)
            elif suspicious_count > 10 or unique_paths_ratio > 0.85:
                severity = max(severity, SeverityLevel.MEDIUM)
                confidence = max(confidence, 0.70)
            else:
                # Minor recon - keep LOW if nothing else elevated
                confidence = max(confidence, 0.60)

        # Check for DDoS - with tiered severity based on realistic thresholds
        burst_rate = features.get('request_burst_rate', 0)
        status_dist = analysis.get('status_distribution', {})
        server_errors = int(status_dist.get('503', 0)) + int(status_dist.get('504', 0))

        if burst_rate > 30 or server_errors > 20:
            if attack_type == AttackType.UNKNOWN:
                attack_type = AttackType.DDOS
            indicators.append(f"Request burst rate: {burst_rate:.2f}/s")
            if server_errors > 0:
                indicators.append(f"Server errors (503/504): {server_errors}")

            # Tiered severity - more realistic thresholds
            if burst_rate > 200 or server_errors > 100:
                severity = SeverityLevel.CRITICAL
                confidence = max(confidence, 0.90)
            elif burst_rate > 100 or server_errors > 50:
                severity = SeverityLevel.HIGH
                confidence = max(confidence, 0.85)
            elif burst_rate > 50 or server_errors > 20:
                severity = max(severity, SeverityLevel.MEDIUM)
                confidence = max(confidence, 0.75)
            else:
                # Elevated traffic but not severe
                severity = max(severity, SeverityLevel.LOW)
                confidence = max(confidence, 0.65)

        # Check for injection - always HIGH or CRITICAL as this is serious
        injection_patterns = ['sql', '--', 'union', 'select', '../', 'etc/passwd', '<script', 'javascript:', 'onerror']
        injection_found = False
        for path in suspicious_paths:
            if any(ind in path.lower() for ind in injection_patterns):
                attack_type = AttackType.INJECTION
                indicators.append(f"Injection pattern detected: {path[:50]}")
                injection_found = True
                break

        if injection_found:
            # Injection attempts are always serious - but severity based on pattern sophistication
            serious_patterns = ['etc/passwd', 'union', '<script', 'javascript:']
            if any(p in ' '.join(suspicious_paths).lower() for p in serious_patterns):
                severity = SeverityLevel.CRITICAL
                confidence = 0.90
            else:
                severity = SeverityLevel.HIGH
                confidence = 0.85

        # Check for suspicious IP behavior - with tiered severity
        geo_score = features.get('geo_anomaly_score', 0)
        top_ips = analysis.get('top_ips', [])

        if geo_score > 0.3:
            if attack_type == AttackType.UNKNOWN:
                attack_type = AttackType.SUSPICIOUS_IP
            indicators.append(f"Geographic anomaly score: {geo_score:.2f}")
            if top_ips:
                indicators.append(f"Top source IP: {top_ips[0][0]}")

            # Tiered based on geo anomaly severity
            if geo_score > 0.9:
                severity = max(severity, SeverityLevel.HIGH)
                confidence = max(confidence, 0.80)
            elif geo_score > 0.7:
                severity = max(severity, SeverityLevel.MEDIUM)
                confidence = max(confidence, 0.70)
            else:
                # Slight geo anomaly - note but keep lower severity
                confidence = max(confidence, 0.60)

        # Check anomaly score - more conservative upgrade to HIGH
        anomaly_score = anomaly.anomaly_score if hasattr(anomaly, 'anomaly_score') else anomaly.get('anomaly_score', 0)

        if anomaly_score > 0.95:
            # Only upgrade to HIGH for very high anomaly scores
            severity = max(severity, SeverityLevel.HIGH)
            confidence = max(confidence, 0.85)
            if attack_type == AttackType.UNKNOWN:
                attack_type = AttackType.ANOMALOUS_TRAFFIC
            indicators.append(f"Very high anomaly score: {anomaly_score:.2f}")
        elif anomaly_score > 0.85:
            # Upgrade to MEDIUM at most for moderately high scores
            severity = max(severity, SeverityLevel.MEDIUM)
            confidence = max(confidence, 0.75)
            if attack_type == AttackType.UNKNOWN:
                attack_type = AttackType.ANOMALOUS_TRAFFIC
            indicators.append(f"Elevated anomaly score: {anomaly_score:.2f}")
        elif anomaly_score > 0.6:
            # Note but don't necessarily upgrade severity
            if attack_type == AttackType.UNKNOWN:
                attack_type = AttackType.ANOMALOUS_TRAFFIC
            indicators.append(f"Anomaly detected: {anomaly_score:.2f}")
            confidence = max(confidence, 0.60)

        # Default if nothing specific found but anomaly detected
        if attack_type == AttackType.UNKNOWN and anomaly_score > 0.5:
            attack_type = AttackType.ANOMALOUS_TRAFFIC
            indicators.append("Minor anomalous traffic pattern detected")
            # Keep LOW severity for unidentified low-score anomalies

        return ThreatClassification(
            attack_type=attack_type,
            confidence=confidence,
            severity=severity,
            indicators=indicators,
            mitre_techniques=MITRE_MAPPINGS.get(attack_type, [])
        )

    def _llm_classification(self, analysis: Dict, anomaly) -> ThreatClassification:
        """LLM-based threat classification"""
        features = anomaly.features if hasattr(anomaly, 'features') else anomaly.get('features', {})
        if hasattr(features, 'model_dump'):
            features = features.model_dump()

        prompt = f"""You are a cybersecurity threat analyst. Classify the following security incident.

LOG ANALYSIS RESULTS:
- Total Logs: {analysis.get('total_logs', 0)}
- Auth Failures: {analysis.get('auth_failures', 0)}
- Suspicious Paths: {analysis.get('suspicious_paths', [])}
- Top IPs: {analysis.get('top_ips', [])}
- Status Distribution: {analysis.get('status_distribution', {})}

ANOMALY FEATURES:
- IP Frequency: {features.get('ip_frequency', 0):.2f}
- Failed Login Ratio: {features.get('failed_login_ratio', 0):.2f}
- Request Burst Rate: {features.get('request_burst_rate', 0):.2f}
- Geo Anomaly Score: {features.get('geo_anomaly_score', 0):.2f}
- Unique Paths Ratio: {features.get('unique_paths_ratio', 0):.2f}
- Error Rate: {features.get('error_rate', 0):.2f}

PREVIOUS ANALYSIS INSIGHTS:
{json.dumps(analysis.get('llm_insights', {}), indent=2)}

SEVERITY GUIDELINES (use proportional severity - not everything is HIGH/CRITICAL):
- LOW: Minor anomalies, first-time events, low metrics (auth_failures<20, burst_rate<50)
- MEDIUM: Elevated concern, repeated patterns, moderate metrics (auth_failures 20-50, burst_rate 50-100)
- HIGH: Confirmed attack patterns, serious metrics (auth_failures 50-100, burst_rate 100-200, injection attempts)
- CRITICAL: Active exploitation, severe impact, extreme metrics (auth_failures>100, burst_rate>200, sophisticated injection)

Classify this threat. Respond with JSON only:
{{
    "attack_type": "BRUTE_FORCE|RECONNAISSANCE|DDOS|INJECTION|SUSPICIOUS_IP|AUTH_FAILURE|ANOMALOUS_TRAFFIC|UNKNOWN",
    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "confidence": 0.0-1.0,
    "indicators": ["list of specific threat indicators"],
    "mitre_techniques": ["T1110", "etc"]
}}"""

        try:
            response = self.groq_client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a threat classification system. Always respond with valid JSON only, no markdown or explanation."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )

            content = response.choices[0].message.content

            # Handle empty response
            if not content or not content.strip():
                print("[ClassificationAgent] Empty LLM response, using rule-based")
                return self._rule_based_classification(analysis, anomaly)

            # Parse JSON - try multiple extraction methods
            try:
                content = content.strip()

                # Try direct JSON parse first
                if content.startswith('{'):
                    result = json.loads(content)
                # Try extracting from markdown code blocks
                elif '```json' in content:
                    json_str = content.split('```json')[1].split('```')[0].strip()
                    result = json.loads(json_str)
                elif '```' in content:
                    json_str = content.split('```')[1].split('```')[0].strip()
                    result = json.loads(json_str)
                else:
                    # Try to find JSON object in the response
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        result = json.loads(content[start:end])
                    else:
                        raise ValueError("No JSON object found in response")

                return ThreatClassification(
                    attack_type=AttackType(result.get('attack_type', 'UNKNOWN')),
                    severity=SeverityLevel(result.get('severity', 'LOW')),
                    confidence=float(result.get('confidence', 0.5)),
                    indicators=result.get('indicators', []),
                    mitre_techniques=result.get('mitre_techniques', [])
                )
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                print(f"[ClassificationAgent] Error parsing LLM response: {e}, content: {content[:200]}")
                return self._rule_based_classification(analysis, anomaly)

        except Exception as e:
            print(f"[ClassificationAgent] LLM classification error: {e}")
            return self._rule_based_classification(analysis, anomaly)


# Singleton instance
threat_classification_agent = ThreatClassificationAgent()
