"""
Log Analysis Agent - Analyzes raw logs and anomaly data
"""
from typing import Dict, Any, List
from datetime import datetime
import json

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from backend.utils import utc_isoformat

from config.settings import settings
from agents.agent_state import AgentState
from backend.models.schemas import IncidentStatus


class LogAnalysisAgent:
    """
    Agent 1: Log Analysis Agent
    Responsibilities:
    - Parse and analyze raw log data
    - Extract patterns and correlations
    - Identify key indicators of compromise
    - Summarize findings for classification
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
            print("Groq not installed, using rule-based analysis")
        except Exception as e:
            print(f"Error initializing Groq: {e}")

    def analyze(self, state: AgentState) -> AgentState:
        """Analyze logs and anomaly data"""
        start_time = datetime.utcnow()

        anomaly = state['anomaly']
        raw_logs = state['raw_logs']

        # Extract key metrics
        analysis = self._extract_metrics(raw_logs, anomaly)

        # Use LLM for deeper analysis if available
        if self.groq_client:
            llm_analysis = self._llm_analysis(raw_logs, anomaly, analysis)
            analysis['llm_insights'] = llm_analysis
        else:
            analysis['llm_insights'] = self._rule_based_insights(analysis)

        # Update state
        state['log_analysis'] = analysis
        state['incident_status'] = IncidentStatus.ANALYZING
        state['agent_logs'] = [{
            'agent': 'LogAnalysisAgent',
            'timestamp': utc_isoformat(),
            'duration_ms': (datetime.utcnow() - start_time).total_seconds() * 1000,
            'action': 'analyze_logs',
            'result': 'success',
            'summary': analysis.get('summary', 'Analysis complete')
        }]

        return state

    def _extract_metrics(self, logs: List[Dict], anomaly) -> Dict[str, Any]:
        """Extract key metrics from logs"""
        if not logs:
            return {'summary': 'No logs to analyze', 'metrics': {}}

        # Count by IP
        ip_counts = {}
        for log in logs:
            ip = log.get('client_ip', 'unknown')
            ip_counts[ip] = ip_counts.get(ip, 0) + 1

        # Count by status code
        status_counts = {}
        for log in logs:
            status = str(log.get('status_code', 0))
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count by path
        path_counts = {}
        for log in logs:
            path = log.get('path', '/')
            path_counts[path] = path_counts.get(path, 0) + 1

        # Auth failures
        auth_failures = sum(1 for log in logs
                          if log.get('status_code') in [401, 403]
                          and ('/auth' in log.get('path', '') or '/login' in log.get('path', '')))

        # Suspicious patterns
        suspicious_paths = [
            log.get('path') for log in logs
            if any(p in log.get('path', '').lower()
                  for p in ['.env', '.git', 'admin', 'config', 'passwd', 'sql', '--'])
        ]

        # Geographic distribution
        geo_counts = {}
        for log in logs:
            country = log.get('geo_country', 'Unknown')
            geo_counts[country] = geo_counts.get(country, 0) + 1

        # Time distribution
        hour_counts = {}
        for log in logs:
            ts = log.get('@timestamp', '')
            if ts:
                try:
                    if isinstance(ts, str):
                        hour = datetime.fromisoformat(ts.replace('Z', '')).hour
                    else:
                        hour = ts.hour
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1
                except:
                    pass

        # Top offending IPs
        top_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            'total_logs': len(logs),
            'unique_ips': len(ip_counts),
            'unique_paths': len(path_counts),
            'top_ips': top_ips,
            'status_distribution': status_counts,
            'auth_failures': auth_failures,
            'suspicious_paths': list(set(suspicious_paths))[:10],
            'geo_distribution': geo_counts,
            'hour_distribution': hour_counts,
            'anomaly_score': anomaly.anomaly_score if hasattr(anomaly, 'anomaly_score') else anomaly.get('anomaly_score', 0),
            'features': anomaly.features.model_dump() if hasattr(anomaly, 'features') and hasattr(anomaly.features, 'model_dump') else anomaly.get('features', {}),
            'summary': self._generate_summary(len(logs), len(ip_counts), auth_failures, len(suspicious_paths))
        }

    def _generate_summary(self, total_logs: int, unique_ips: int, auth_failures: int, suspicious_count: int) -> str:
        """Generate human-readable summary"""
        parts = [f"Analyzed {total_logs} logs from {unique_ips} unique IPs."]

        if auth_failures > 5:
            parts.append(f"Detected {auth_failures} authentication failures.")

        if suspicious_count > 0:
            parts.append(f"Found {suspicious_count} suspicious path access attempts.")

        return " ".join(parts)

    def _llm_analysis(self, logs: List[Dict], anomaly, metrics: Dict) -> Dict[str, Any]:
        """Use Groq LLM for deeper analysis"""
        # Prepare context
        sample_logs = logs[:20]  # Limit for context size

        prompt = f"""You are a SOC analyst. Analyze the following security log data and provide insights.

ANOMALY DETECTION RESULT:
- Anomaly Score: {anomaly.anomaly_score if hasattr(anomaly, 'anomaly_score') else anomaly.get('anomaly_score', 0):.2f}
- Is Anomaly: {anomaly.is_anomaly if hasattr(anomaly, 'is_anomaly') else anomaly.get('is_anomaly', False)}
- Source IPs: {anomaly.source_ips if hasattr(anomaly, 'source_ips') else anomaly.get('source_ips', [])}

KEY METRICS:
- Total Logs: {metrics['total_logs']}
- Unique IPs: {metrics['unique_ips']}
- Auth Failures: {metrics['auth_failures']}
- Top IPs: {metrics['top_ips']}
- Status Distribution: {metrics['status_distribution']}
- Suspicious Paths: {metrics['suspicious_paths']}

SAMPLE LOGS:
{json.dumps(sample_logs[:5], indent=2, default=str)}

Provide a JSON response with:
1. "threat_indicators": list of specific threat indicators found
2. "attack_patterns": identified attack patterns
3. "risk_assessment": LOW/MEDIUM/HIGH/CRITICAL
4. "recommendations": brief recommendations
5. "confidence": 0.0-1.0

Respond ONLY with valid JSON."""

        try:
            response = self.groq_client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a SOC analyst. Always respond with valid JSON only, no markdown or explanation."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )

            content = response.choices[0].message.content

            # Handle empty response
            if not content or not content.strip():
                print("[LogAnalysisAgent] Empty LLM response, using rule-based")
                return self._rule_based_insights(metrics)

            content = content.strip()

            # Try to parse JSON from response
            try:
                if content.startswith('{'):
                    return json.loads(content)
                elif '```json' in content:
                    json_str = content.split('```json')[1].split('```')[0].strip()
                    return json.loads(json_str)
                elif '```' in content:
                    json_str = content.split('```')[1].split('```')[0].strip()
                    return json.loads(json_str)
                else:
                    # Try to find JSON object
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        return json.loads(content[start:end])
                return {'raw_response': content}
            except json.JSONDecodeError as e:
                print(f"[LogAnalysisAgent] JSON parse error: {e}")
                return self._rule_based_insights(metrics)

        except Exception as e:
            print(f"[LogAnalysisAgent] LLM error: {e}")
            return self._rule_based_insights(metrics)

    def _rule_based_insights(self, metrics: Dict) -> Dict[str, Any]:
        """Fallback rule-based insights"""
        threat_indicators = []
        attack_patterns = []
        risk = "LOW"

        # Check auth failures
        if metrics.get('auth_failures', 0) > 10:
            threat_indicators.append("High rate of authentication failures")
            attack_patterns.append("Potential brute force attack")
            risk = "HIGH"
        elif metrics.get('auth_failures', 0) > 5:
            threat_indicators.append("Elevated authentication failures")
            risk = "MEDIUM"

        # Check suspicious paths
        suspicious = metrics.get('suspicious_paths', [])
        if suspicious:
            threat_indicators.append(f"Suspicious path access: {suspicious[:3]}")
            attack_patterns.append("Reconnaissance/scanning activity")
            if risk != "HIGH":
                risk = "MEDIUM"

        # Check IP concentration
        top_ips = metrics.get('top_ips', [])
        if top_ips and top_ips[0][1] > 50:
            threat_indicators.append(f"High request volume from single IP: {top_ips[0][0]}")
            attack_patterns.append("Potential DoS or automated attack")
            risk = "HIGH"

        # Check error rate
        status_dist = metrics.get('status_distribution', {})
        total = sum(int(v) for v in status_dist.values())
        errors = sum(int(v) for k, v in status_dist.items() if k.startswith('4') or k.startswith('5'))
        if total > 0 and errors / total > 0.5:
            threat_indicators.append("High error rate detected")
            risk = max(risk, "MEDIUM")

        return {
            'threat_indicators': threat_indicators,
            'attack_patterns': attack_patterns,
            'risk_assessment': risk,
            'recommendations': ['Investigate source IPs', 'Review authentication logs', 'Check for data exfiltration'],
            'confidence': 0.7 if threat_indicators else 0.5
        }


# Singleton instance
log_analysis_agent = LogAnalysisAgent()
