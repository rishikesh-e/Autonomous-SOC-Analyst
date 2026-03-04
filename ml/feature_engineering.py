"""
Feature Engineering for Anomaly Detection
"""
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from collections import Counter
import math

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from backend.models.schemas import AnomalyFeatures


class FeatureEngineer:
    """Extract and engineer features from raw log data for anomaly detection"""

    def __init__(self):
        self.ip_history: Dict[str, List[datetime]] = {}
        self.baseline_stats: Dict[str, float] = {}

    def calculate_entropy(self, values: List[Any]) -> float:
        """Calculate Shannon entropy of a distribution"""
        if not values:
            return 0.0

        counter = Counter(values)
        total = len(values)
        entropy = 0.0

        for count in counter.values():
            if count > 0:
                prob = count / total
                entropy -= prob * math.log2(prob)

        return entropy

    def calculate_ip_frequency(self, logs: List[Dict], ip: str) -> float:
        """Calculate request frequency for a specific IP"""
        if not logs:
            return 0.0

        ip_logs = [log for log in logs if log.get('client_ip') == ip]
        if len(ip_logs) < 2:
            return 0.0

        timestamps = []
        for log in ip_logs:
            ts = log.get('@timestamp') or log.get('timestamp')
            if ts:
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00').replace('+00:00', ''))
                timestamps.append(ts)
        timestamps.sort()

        if len(timestamps) < 2:
            return 0.0

        time_span = (timestamps[-1] - timestamps[0]).total_seconds()
        if time_span == 0:
            return float(len(ip_logs))  # All requests at same time - very suspicious

        return len(ip_logs) / time_span  # Requests per second

    def calculate_failed_login_ratio(self, logs: List[Dict]) -> float:
        """Calculate ratio of failed login attempts"""
        auth_logs = [log for log in logs if '/auth' in log.get('path', '') or '/login' in log.get('path', '')]

        if not auth_logs:
            return 0.0

        failed = sum(1 for log in auth_logs if log.get('status_code') in [401, 403])
        return failed / len(auth_logs)

    def calculate_time_deviation(self, logs: List[Dict]) -> float:
        """Calculate deviation from normal time patterns (hour-based)"""
        if not logs:
            return 0.0

        hours = []
        for log in logs:
            ts = log.get('@timestamp')
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace('Z', '+00:00').replace('+00:00', ''))
            hours.append(ts.hour)

        if not hours:
            return 0.0

        # Normal business hours: 8-18
        business_hours = sum(1 for h in hours if 8 <= h <= 18)
        off_hours = len(hours) - business_hours

        # High deviation if many requests outside business hours
        return off_hours / len(hours) if hours else 0.0

    def calculate_status_code_entropy(self, logs: List[Dict]) -> float:
        """Calculate entropy of status code distribution"""
        status_codes = [log.get('status_code', 200) for log in logs]
        return self.calculate_entropy(status_codes)

    def calculate_request_burst_rate(self, logs: List[Dict], window_seconds: int = 60) -> float:
        """Calculate maximum request rate in any window"""
        if not logs:
            return 0.0

        timestamps = []
        for log in logs:
            ts = log.get('@timestamp')
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace('Z', '+00:00').replace('+00:00', ''))
            timestamps.append(ts)

        timestamps.sort()

        if len(timestamps) < 2:
            return 0.0

        max_rate = 0.0
        for i, ts in enumerate(timestamps):
            window_end = ts + timedelta(seconds=window_seconds)
            count = sum(1 for t in timestamps[i:] if t <= window_end)
            rate = count / window_seconds
            max_rate = max(max_rate, rate)

        return max_rate

    def calculate_geo_anomaly_score(self, logs: List[Dict]) -> float:
        """Calculate geographic anomaly score based on country distribution"""
        suspicious_countries = {'CN', 'RU', 'KP', 'IR'}

        countries = [log.get('geo_country') for log in logs if log.get('geo_country')]

        if not countries:
            return 0.0

        suspicious_count = sum(1 for c in countries if c in suspicious_countries)
        unknown_count = sum(1 for c in countries if c == 'Unknown' or c is None)

        # Score based on suspicious + unknown countries
        return (suspicious_count + unknown_count * 0.5) / len(countries)

    def calculate_unique_paths_ratio(self, logs: List[Dict]) -> float:
        """Calculate ratio of unique paths (high = possible reconnaissance)"""
        if not logs:
            return 0.0

        paths = [log.get('path', '') for log in logs]
        unique_paths = len(set(paths))

        return unique_paths / len(logs)

    def calculate_avg_latency(self, logs: List[Dict]) -> float:
        """Calculate average latency"""
        latencies = [log.get('latency_ms', 0) for log in logs if log.get('latency_ms')]
        return np.mean(latencies) if latencies else 0.0

    def calculate_error_rate(self, logs: List[Dict]) -> float:
        """Calculate error rate (4xx + 5xx)"""
        if not logs:
            return 0.0

        errors = sum(1 for log in logs if log.get('status_code', 200) >= 400)
        return errors / len(logs)

    def extract_features(self, logs: List[Dict]) -> AnomalyFeatures:
        """Extract all features from a window of logs"""
        # Get the most frequent IP for IP-specific features
        ip_counts = Counter(log.get('client_ip') for log in logs)
        top_ip = ip_counts.most_common(1)[0][0] if ip_counts else None

        features = AnomalyFeatures(
            ip_frequency=self.calculate_ip_frequency(logs, top_ip) if top_ip else 0.0,
            failed_login_ratio=self.calculate_failed_login_ratio(logs),
            time_deviation=self.calculate_time_deviation(logs),
            status_code_entropy=self.calculate_status_code_entropy(logs),
            request_burst_rate=self.calculate_request_burst_rate(logs),
            geo_anomaly_score=self.calculate_geo_anomaly_score(logs),
            unique_paths_ratio=self.calculate_unique_paths_ratio(logs),
            avg_latency=self.calculate_avg_latency(logs),
            error_rate=self.calculate_error_rate(logs)
        )

        return features

    def features_to_array(self, features: AnomalyFeatures) -> np.ndarray:
        """Convert features to numpy array for ML model"""
        return np.array([
            features.ip_frequency,
            features.failed_login_ratio,
            features.time_deviation,
            features.status_code_entropy,
            features.request_burst_rate,
            features.geo_anomaly_score,
            features.unique_paths_ratio,
            features.avg_latency / 1000.0,  # Normalize latency to seconds
            features.error_rate
        ])

    def extract_per_ip_features(self, logs: List[Dict]) -> Dict[str, AnomalyFeatures]:
        """Extract features per unique IP"""
        ip_logs: Dict[str, List[Dict]] = {}

        for log in logs:
            ip = log.get('client_ip')
            if ip:
                if ip not in ip_logs:
                    ip_logs[ip] = []
                ip_logs[ip].append(log)

        ip_features = {}
        for ip, ip_log_list in ip_logs.items():
            if len(ip_log_list) >= 3:  # Minimum logs for meaningful features
                ip_features[ip] = self.extract_features(ip_log_list)

        return ip_features


# Singleton instance
feature_engineer = FeatureEngineer()
