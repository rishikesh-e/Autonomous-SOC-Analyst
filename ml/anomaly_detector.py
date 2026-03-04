"""
Anomaly Detection using Isolation Forest
"""
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import pickle
from pathlib import Path
import json

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from config.settings import settings
from backend.models.schemas import AnomalyResult, AnomalyFeatures
from backend.utils import utc_isoformat
from ml.feature_engineering import FeatureEngineer, feature_engineer


class AnomalyDetector:
    """Isolation Forest-based anomaly detector for SOC logs"""

    def __init__(self, contamination: float = 0.1, model_path: str = "data/anomaly_model.pkl"):
        self.contamination = contamination
        self.model_path = Path(model_path)
        self.model: Optional[IsolationForest] = None
        self.scaler = StandardScaler()
        self.feature_engineer = feature_engineer
        self.is_fitted = False
        self.training_history: List[Dict] = []

        # Load existing model if available
        self._load_model()

    def _load_model(self):
        """Load pre-trained model if exists"""
        if self.model_path.exists():
            try:
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data['model']
                    self.scaler = data['scaler']
                    self.is_fitted = True
                    print(f"Loaded model from {self.model_path}")
            except Exception as e:
                print(f"Error loading model: {e}")
                self._initialize_model()
        else:
            self._initialize_model()

    def _initialize_model(self):
        """Initialize a new Isolation Forest model"""
        self.model = IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            max_samples='auto',
            random_state=42,
            n_jobs=-1
        )
        self.is_fitted = False

    def save_model(self):
        """Save the trained model"""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler
            }, f)
        print(f"Model saved to {self.model_path}")

    def fit(self, logs_windows: List[List[Dict]]):
        """Train the model on historical log windows"""
        if not logs_windows:
            print("No training data provided")
            return

        # Extract features from each window
        feature_arrays = []
        for logs in logs_windows:
            if logs:
                features = self.feature_engineer.extract_features(logs)
                feature_array = self.feature_engineer.features_to_array(features)
                feature_arrays.append(feature_array)

        if not feature_arrays:
            print("No valid features extracted")
            return

        X = np.array(feature_arrays)

        # Fit scaler and transform
        X_scaled = self.scaler.fit_transform(X)

        # Fit Isolation Forest
        self.model.fit(X_scaled)
        self.is_fitted = True

        self.training_history.append({
            'timestamp': utc_isoformat(),
            'samples': len(X),
            'features': X.shape[1] if len(X.shape) > 1 else 1
        })

        self.save_model()
        print(f"Model trained on {len(X)} samples")

    def partial_fit(self, logs: List[Dict]):
        """Incrementally update the model with new data"""
        if not logs:
            return

        features = self.feature_engineer.extract_features(logs)
        feature_array = self.feature_engineer.features_to_array(features)

        # For now, just retrain if we have enough history
        # In production, you might want online learning approaches
        self.training_history.append({
            'timestamp': utc_isoformat(),
            'features': feature_array.tolist()
        })

    def predict(self, logs: List[Dict]) -> AnomalyResult:
        """Detect anomalies in a log window"""
        if not logs:
            return self._empty_result()

        # Extract features
        features = self.feature_engineer.extract_features(logs)
        feature_array = self.feature_engineer.features_to_array(features)

        # Get timestamps for window bounds
        timestamps = []
        for log in logs:
            ts = log.get('@timestamp')
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace('Z', '+00:00').replace('+00:00', ''))
            timestamps.append(ts)

        window_start = min(timestamps) if timestamps else datetime.utcnow()
        window_end = max(timestamps) if timestamps else datetime.utcnow()

        # Extract source IPs and paths
        source_ips = list(set(log.get('client_ip', '') for log in logs if log.get('client_ip')))
        affected_paths = list(set(log.get('path', '') for log in logs if log.get('path')))

        # If model not fitted, use rule-based detection
        if not self.is_fitted:
            is_anomaly, score = self._rule_based_detection(features)
        else:
            # Scale and predict
            X = feature_array.reshape(1, -1)
            try:
                X_scaled = self.scaler.transform(X)
                prediction = self.model.predict(X_scaled)
                score = -self.model.score_samples(X_scaled)[0]  # Higher = more anomalous

                # Normalize score to 0-1 range
                score = min(1.0, max(0.0, (score + 0.5) / 1.0))
                is_anomaly = prediction[0] == -1
            except Exception as e:
                print(f"Prediction error: {e}")
                is_anomaly, score = self._rule_based_detection(features)

        return AnomalyResult(
            timestamp=datetime.utcnow(),
            anomaly_score=float(score),
            is_anomaly=is_anomaly,
            features=features,
            source_ips=source_ips[:10],  # Limit to top 10
            affected_paths=affected_paths[:10],
            window_start=window_start,
            window_end=window_end
        )

    def predict_per_ip(self, logs: List[Dict]) -> Dict[str, AnomalyResult]:
        """Detect anomalies per IP address"""
        ip_features = self.feature_engineer.extract_per_ip_features(logs)
        results = {}

        for ip, features in ip_features.items():
            feature_array = self.feature_engineer.features_to_array(features)

            # Get IP-specific logs
            ip_logs = [log for log in logs if log.get('client_ip') == ip]

            timestamps = []
            for log in ip_logs:
                ts = log.get('@timestamp')
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00').replace('+00:00', ''))
                timestamps.append(ts)

            window_start = min(timestamps) if timestamps else datetime.utcnow()
            window_end = max(timestamps) if timestamps else datetime.utcnow()

            paths = list(set(log.get('path', '') for log in ip_logs))

            if not self.is_fitted:
                is_anomaly, score = self._rule_based_detection(features)
            else:
                X = feature_array.reshape(1, -1)
                try:
                    X_scaled = self.scaler.transform(X)
                    prediction = self.model.predict(X_scaled)
                    score = -self.model.score_samples(X_scaled)[0]
                    score = min(1.0, max(0.0, (score + 0.5) / 1.0))
                    is_anomaly = prediction[0] == -1
                except Exception:
                    is_anomaly, score = self._rule_based_detection(features)

            results[ip] = AnomalyResult(
                timestamp=datetime.utcnow(),
                anomaly_score=float(score),
                is_anomaly=is_anomaly,
                features=features,
                source_ips=[ip],
                affected_paths=paths[:10],
                window_start=window_start,
                window_end=window_end
            )

        return results

    def _rule_based_detection(self, features: AnomalyFeatures) -> Tuple[bool, float]:
        """Fallback rule-based detection when model is not trained"""
        score = 0.0
        anomaly_indicators = 0

        # High IP frequency (> 5 requests/second)
        if features.ip_frequency > 5:
            score += 0.2
            anomaly_indicators += 1

        # High failed login ratio
        if features.failed_login_ratio > 0.5:
            score += 0.25
            anomaly_indicators += 1

        # Unusual time patterns
        if features.time_deviation > 0.7:
            score += 0.1
            anomaly_indicators += 1

        # Low status code entropy (attacking single endpoint)
        if features.status_code_entropy < 0.5 and features.error_rate > 0.3:
            score += 0.15
            anomaly_indicators += 1

        # High burst rate
        if features.request_burst_rate > 10:
            score += 0.2
            anomaly_indicators += 1

        # Suspicious geography
        if features.geo_anomaly_score > 0.5:
            score += 0.15
            anomaly_indicators += 1

        # High unique paths ratio (reconnaissance)
        if features.unique_paths_ratio > 0.8:
            score += 0.15
            anomaly_indicators += 1

        # High error rate
        if features.error_rate > 0.5:
            score += 0.15
            anomaly_indicators += 1

        # High latency (possible DoS)
        if features.avg_latency > 1000:
            score += 0.1
            anomaly_indicators += 1

        # Normalize score
        score = min(1.0, score)

        # Anomaly if score > 0.5 or multiple indicators
        is_anomaly = score > 0.5 or anomaly_indicators >= 3

        return is_anomaly, score

    def _empty_result(self) -> AnomalyResult:
        """Return an empty result for no data"""
        now = datetime.utcnow()
        return AnomalyResult(
            timestamp=now,
            anomaly_score=0.0,
            is_anomaly=False,
            features=AnomalyFeatures(
                ip_frequency=0.0,
                failed_login_ratio=0.0,
                time_deviation=0.0,
                status_code_entropy=0.0,
                request_burst_rate=0.0,
                geo_anomaly_score=0.0,
                unique_paths_ratio=0.0,
                avg_latency=0.0,
                error_rate=0.0
            ),
            source_ips=[],
            affected_paths=[],
            window_start=now,
            window_end=now
        )

    def get_feature_importance(self) -> Dict[str, float]:
        """Get relative importance of each feature"""
        feature_names = [
            'ip_frequency',
            'failed_login_ratio',
            'time_deviation',
            'status_code_entropy',
            'request_burst_rate',
            'geo_anomaly_score',
            'unique_paths_ratio',
            'avg_latency',
            'error_rate'
        ]

        # Isolation Forest doesn't have direct feature importances
        # Return heuristic importances based on domain knowledge
        return {
            'ip_frequency': 0.15,
            'failed_login_ratio': 0.18,
            'time_deviation': 0.08,
            'status_code_entropy': 0.10,
            'request_burst_rate': 0.15,
            'geo_anomaly_score': 0.12,
            'unique_paths_ratio': 0.10,
            'avg_latency': 0.05,
            'error_rate': 0.07
        }


# Singleton instance
anomaly_detector = AnomalyDetector(contamination=settings.ANOMALY_CONTAMINATION)
