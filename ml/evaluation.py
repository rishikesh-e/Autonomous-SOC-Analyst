#!/usr/bin/env python3
"""
Performance Evaluation Module
Calculates precision, recall, F1-score, ROC-AUC, false positive rate, and detection latency.

IMPORTANT: This module implements proper train/test separation to avoid overfitting.
- Uses holdout evaluation with temporal split
- Generates FRESH test data not seen during training
- Uses realistic class distributions (not 50/50)
"""
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, roc_curve
)
from sklearn.model_selection import train_test_split
import json
from pathlib import Path
import random

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from config.settings import settings
from backend.models.schemas import EvaluationMetrics
from backend.services.elasticsearch_service import get_es_service
from backend.utils import utc_isoformat


class Evaluator:
    """
    Evaluates the performance of the anomaly detection system.

    CRITICAL: This evaluator ensures proper train/test separation to provide
    realistic performance metrics and avoid overfitting.
    """

    def __init__(self):
        self.results_path = Path("data/evaluation_results.json")
        self.results_path.parent.mkdir(parents=True, exist_ok=True)
        self._test_data_seed = None  # Track random seed for reproducibility

    def evaluate_with_holdout(
        self,
        num_test_samples: int = 100,
        attack_ratio: float = 0.1,  # Realistic: 10% attacks, 90% normal
        random_seed: int = None
    ) -> EvaluationMetrics:
        """
        Evaluate using FRESH holdout data not seen during training.

        This is the RECOMMENDED evaluation method as it:
        1. Generates completely new test data
        2. Uses realistic attack/normal ratio (default 10% attacks)
        3. Does not contaminate training data

        Args:
            num_test_samples: Number of test windows to generate
            attack_ratio: Proportion of attack samples (default 0.1 = 10%)
            random_seed: Random seed for reproducibility

        Returns:
            EvaluationMetrics with realistic performance estimates
        """
        from scripts.log_generator import LogGenerator
        from ml.anomaly_detector import anomaly_detector

        # Set seed for reproducibility
        if random_seed is not None:
            random.seed(random_seed)
            np.random.seed(random_seed)
            self._test_data_seed = random_seed

        generator = LogGenerator()
        windows = []
        labels = []

        # Calculate number of each type
        num_attacks = int(num_test_samples * attack_ratio)
        num_normal = num_test_samples - num_attacks

        print(f"[Evaluation] Generating {num_normal} normal + {num_attacks} attack test samples...")

        # Generate normal windows (majority class)
        for _ in range(num_normal):
            # Generate fresh normal traffic with some variation
            normal_logs = []
            num_logs = random.randint(30, 70)  # Variable window size
            for _ in range(num_logs):
                log = generator.generate_normal_log()
                normal_logs.append(log)
            windows.append(normal_logs)
            labels.append(0)

        # Generate attack windows (minority class - realistic)
        attack_funcs = [
            ('brute_force', generator.generate_brute_force_attack),
            ('traffic_burst', generator.generate_traffic_burst),
            ('reconnaissance', generator.generate_reconnaissance),
            ('injection', generator.generate_injection_attempt),
            ('suspicious_ip', generator.generate_suspicious_ip_behavior),
        ]

        for i in range(num_attacks):
            attack_name, attack_func = attack_funcs[i % len(attack_funcs)]
            attack_logs = attack_func()

            # Mix with varying amounts of normal traffic (more realistic)
            num_normal_mixed = random.randint(10, 40)
            mixed_logs = [generator.generate_normal_log() for _ in range(num_normal_mixed)]

            # Add attack logs (variable amount)
            num_attack_logs = min(len(attack_logs), random.randint(10, 30))
            mixed_logs.extend(attack_logs[:num_attack_logs])

            # Shuffle to make detection harder
            random.shuffle(mixed_logs)

            windows.append(mixed_logs)
            labels.append(1)

        # Shuffle all samples
        combined = list(zip(windows, labels))
        random.shuffle(combined)
        windows, labels = zip(*combined)
        windows = list(windows)
        labels = list(labels)

        print(f"[Evaluation] Running predictions on {len(windows)} test samples...")

        # Run predictions
        predictions = []
        scores = []
        latencies = []

        for window in windows:
            start_time = datetime.utcnow()
            result = anomaly_detector.predict(window)
            end_time = datetime.utcnow()

            latency = (end_time - start_time).total_seconds() * 1000
            predictions.append(1 if result.is_anomaly else 0)
            scores.append(result.anomaly_score)
            latencies.append(latency)

        metrics = self._calculate_metrics(
            y_true=np.array(labels),
            y_pred=np.array(predictions),
            y_scores=np.array(scores),
            latencies=latencies
        )

        # Add warning if metrics look suspicious
        if metrics.f1_score == 1.0 and metrics.false_positives == 0 and metrics.false_negatives == 0:
            print("\n[WARNING] Perfect scores detected! This may indicate:")
            print("  - Test data is too easy/synthetic")
            print("  - Model might be overfitting")
            print("  - Consider using evaluate_from_elasticsearch_holdout() with real data")

        return metrics

    def evaluate_from_elasticsearch_holdout(
        self,
        train_hours: int = 24,
        test_hours: int = 6,
        gap_hours: int = 1,
        attack_ips: Optional[List[str]] = None
    ) -> EvaluationMetrics:
        """
        Evaluate using temporal holdout from Elasticsearch data.

        Uses a GAP between training and test periods to prevent data leakage.

        Timeline:
        [------ TRAINING DATA ------][-- GAP --][---- TEST DATA ----]

        Args:
            train_hours: Hours of data for training (default 24)
            test_hours: Hours of data for testing (default 6)
            gap_hours: Gap between train and test to prevent leakage (default 1)
            attack_ips: Known attack IPs for labeling

        Returns:
            EvaluationMetrics from holdout evaluation
        """
        from ml.anomaly_detector import AnomalyDetector

        now = datetime.utcnow()

        # Define time periods with gap
        test_end = now
        test_start = now - timedelta(hours=test_hours)
        train_end = test_start - timedelta(hours=gap_hours)  # GAP prevents leakage
        train_start = train_end - timedelta(hours=train_hours)

        print(f"[Evaluation] Temporal Split:")
        print(f"  Training: {train_start.isoformat()} to {train_end.isoformat()}")
        print(f"  Gap:      {train_end.isoformat()} to {test_start.isoformat()}")
        print(f"  Testing:  {test_start.isoformat()} to {test_end.isoformat()}")

        es_service = get_es_service()

        # Get training data
        train_logs = es_service.get_logs_window(train_start, train_end, size=10000)
        if len(train_logs) < 100:
            print(f"[WARNING] Only {len(train_logs)} training logs available")
            return self._empty_metrics()

        # Get test data (SEPARATE from training)
        test_logs = es_service.get_logs_window(test_start, test_end, size=5000)
        if len(test_logs) < 50:
            print(f"[WARNING] Only {len(test_logs)} test logs available")
            return self._empty_metrics()

        print(f"[Evaluation] Train logs: {len(train_logs)}, Test logs: {len(test_logs)}")

        # Create a FRESH model trained only on training data
        eval_detector = AnomalyDetector(
            contamination=settings.ANOMALY_CONTAMINATION,
            model_path="data/eval_model_temp.pkl"
        )

        # Train on training windows
        window_size = 50
        train_windows = []
        for i in range(0, len(train_logs), window_size):
            window = train_logs[i:i+window_size]
            if len(window) >= 10:
                train_windows.append(window)

        if train_windows:
            eval_detector.fit(train_windows)
        else:
            print("[WARNING] No valid training windows")
            return self._empty_metrics()

        # Default known attacker IPs if not provided
        if attack_ips is None:
            attack_ips = [f"45.33.32.{i}" for i in range(1, 10)] + [
                "185.220.101.1", "185.220.101.2", "185.220.101.3"
            ]
        attack_ip_set = set(attack_ips)

        # Create test windows and labels
        test_windows = []
        labels = []

        for i in range(0, len(test_logs), window_size):
            window = test_logs[i:i+window_size]
            if len(window) < 10:
                continue

            test_windows.append(window)

            # Label as attack if any log is from known attack IP
            has_attack = any(
                log.get('client_ip') in attack_ip_set
                for log in window
            )
            labels.append(1 if has_attack else 0)

        if not test_windows:
            print("[WARNING] No valid test windows")
            return self._empty_metrics()

        # Run predictions on TEST data using model trained on TRAINING data
        predictions = []
        scores = []
        latencies = []

        for window in test_windows:
            start_time = datetime.utcnow()
            result = eval_detector.predict(window)
            end_time = datetime.utcnow()

            latency = (end_time - start_time).total_seconds() * 1000
            predictions.append(1 if result.is_anomaly else 0)
            scores.append(result.anomaly_score)
            latencies.append(latency)

        # Clean up temp model file
        try:
            Path("data/eval_model_temp.pkl").unlink()
        except:
            pass

        metrics = self._calculate_metrics(
            y_true=np.array(labels),
            y_pred=np.array(predictions),
            y_scores=np.array(scores),
            latencies=latencies
        )

        # Report class distribution
        num_attacks = sum(labels)
        num_normal = len(labels) - num_attacks
        print(f"[Evaluation] Class distribution: {num_normal} normal, {num_attacks} attacks ({100*num_attacks/len(labels):.1f}% attack rate)")

        return metrics

    def evaluate_with_cross_validation(
        self,
        num_folds: int = 5,
        num_samples: int = 200,
        attack_ratio: float = 0.15
    ) -> Dict[str, Any]:
        """
        Perform k-fold cross-validation for more robust evaluation.

        Args:
            num_folds: Number of CV folds
            num_samples: Total samples to generate
            attack_ratio: Proportion of attacks

        Returns:
            Dictionary with mean metrics and standard deviations
        """
        from scripts.log_generator import LogGenerator
        from ml.anomaly_detector import AnomalyDetector

        generator = LogGenerator()

        # Generate all data
        all_windows = []
        all_labels = []

        num_attacks = int(num_samples * attack_ratio)
        num_normal = num_samples - num_attacks

        # Generate normal
        for _ in range(num_normal):
            logs = [generator.generate_normal_log() for _ in range(random.randint(30, 60))]
            all_windows.append(logs)
            all_labels.append(0)

        # Generate attacks
        attack_funcs = [
            generator.generate_brute_force_attack,
            generator.generate_traffic_burst,
            generator.generate_reconnaissance,
            generator.generate_injection_attempt,
            generator.generate_suspicious_ip_behavior,
        ]

        for i in range(num_attacks):
            attack_func = attack_funcs[i % len(attack_funcs)]
            attack_logs = attack_func()
            mixed = [generator.generate_normal_log() for _ in range(20)]
            mixed.extend(attack_logs[:25])
            random.shuffle(mixed)
            all_windows.append(mixed)
            all_labels.append(1)

        # Shuffle
        combined = list(zip(all_windows, all_labels))
        random.shuffle(combined)
        all_windows, all_labels = zip(*combined)
        all_windows = list(all_windows)
        all_labels = list(all_labels)

        # K-fold CV
        fold_size = len(all_windows) // num_folds
        fold_metrics = []

        print(f"[Evaluation] Running {num_folds}-fold cross-validation...")

        for fold in range(num_folds):
            # Split into train/test for this fold
            test_start = fold * fold_size
            test_end = test_start + fold_size

            test_windows = all_windows[test_start:test_end]
            test_labels = all_labels[test_start:test_end]

            train_windows = all_windows[:test_start] + all_windows[test_end:]

            # Train fresh model for this fold
            fold_detector = AnomalyDetector(
                contamination=settings.ANOMALY_CONTAMINATION,
                model_path=f"data/cv_model_fold{fold}.pkl"
            )
            fold_detector.fit(train_windows)

            # Evaluate
            predictions = []
            scores = []

            for window in test_windows:
                result = fold_detector.predict(window)
                predictions.append(1 if result.is_anomaly else 0)
                scores.append(result.anomaly_score)

            # Calculate fold metrics
            metrics = self._calculate_metrics(
                y_true=np.array(test_labels),
                y_pred=np.array(predictions),
                y_scores=np.array(scores),
                latencies=[0]  # Skip latency for CV
            )
            fold_metrics.append(metrics)

            print(f"  Fold {fold+1}: F1={metrics.f1_score:.3f}, Precision={metrics.precision:.3f}, Recall={metrics.recall:.3f}")

            # Clean up
            try:
                Path(f"data/cv_model_fold{fold}.pkl").unlink()
            except:
                pass

        # Calculate mean and std
        f1_scores = [m.f1_score for m in fold_metrics]
        precision_scores = [m.precision for m in fold_metrics]
        recall_scores = [m.recall for m in fold_metrics]

        return {
            "num_folds": num_folds,
            "f1_mean": np.mean(f1_scores),
            "f1_std": np.std(f1_scores),
            "precision_mean": np.mean(precision_scores),
            "precision_std": np.std(precision_scores),
            "recall_mean": np.mean(recall_scores),
            "recall_std": np.std(recall_scores),
            "fold_metrics": [m.model_dump() for m in fold_metrics]
        }

    def generate_labeled_dataset(
        self,
        normal_logs: List[Dict],
        attack_logs: List[Dict]
    ) -> Tuple[List[Dict], List[int]]:
        """
        Create a labeled dataset from normal and attack logs.
        Returns: (combined_logs, labels) where 1=attack, 0=normal
        """
        all_logs = []
        labels = []

        for log in normal_logs:
            all_logs.append(log)
            labels.append(0)

        for log in attack_logs:
            all_logs.append(log)
            labels.append(1)

        return all_logs, labels

    def evaluate_window_predictions(
        self,
        windows: List[List[Dict]],
        labels: List[int]
    ) -> EvaluationMetrics:
        """
        Evaluate anomaly detection on labeled windows.
        NOTE: Use evaluate_with_holdout() instead for proper train/test separation.
        """
        from ml.anomaly_detector import anomaly_detector

        if len(windows) != len(labels):
            raise ValueError("Windows and labels must have same length")

        predictions = []
        scores = []
        latencies = []

        for window in windows:
            start_time = datetime.utcnow()
            result = anomaly_detector.predict(window)
            end_time = datetime.utcnow()

            latency = (end_time - start_time).total_seconds() * 1000
            predictions.append(1 if result.is_anomaly else 0)
            scores.append(result.anomaly_score)
            latencies.append(latency)

        return self._calculate_metrics(
            y_true=np.array(labels),
            y_pred=np.array(predictions),
            y_scores=np.array(scores),
            latencies=latencies
        )

    def evaluate_from_elasticsearch(
        self,
        hours: int = 24,
        attack_ips: Optional[List[str]] = None
    ) -> EvaluationMetrics:
        """
        [DEPRECATED] This method may cause overfitting as it evaluates on training data.
        Use evaluate_from_elasticsearch_holdout() instead.
        """
        print("\n[WARNING] evaluate_from_elasticsearch() is deprecated due to overfitting risk.")
        print("[WARNING] Use evaluate_from_elasticsearch_holdout() or evaluate_with_holdout() instead.\n")

        from ml.anomaly_detector import anomaly_detector

        end = datetime.utcnow()
        start = end - timedelta(hours=hours)

        logs = get_es_service().get_logs_window(start, end, size=10000)

        if not logs:
            return self._empty_metrics()

        if attack_ips is None:
            attack_ips = [f"45.33.32.{i}" for i in range(1, 10)] + [
                "185.220.101.1", "185.220.101.2", "185.220.101.3"
            ]

        attack_ip_set = set(attack_ips)

        window_size = 50
        windows = []
        labels = []

        for i in range(0, len(logs), window_size):
            window = logs[i:i+window_size]
            if len(window) < 10:
                continue

            windows.append(window)
            has_attack = any(
                log.get('client_ip') in attack_ip_set
                for log in window
            )
            labels.append(1 if has_attack else 0)

        if not windows:
            return self._empty_metrics()

        return self.evaluate_window_predictions(windows, labels)

    def evaluate_with_simulated_data(self, num_samples: int = 100) -> EvaluationMetrics:
        """
        [DEPRECATED] Uses unrealistic 50/50 distribution.
        Use evaluate_with_holdout() with attack_ratio parameter instead.
        """
        print("\n[WARNING] evaluate_with_simulated_data() uses unrealistic 50/50 distribution.")
        print("[WARNING] Use evaluate_with_holdout(attack_ratio=0.1) for realistic evaluation.\n")

        # Redirect to holdout with 50/50 for backwards compatibility
        return self.evaluate_with_holdout(
            num_test_samples=num_samples,
            attack_ratio=0.5  # Keep 50/50 for backwards compatibility
        )

    def _calculate_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_scores: np.ndarray,
        latencies: List[float]
    ) -> EvaluationMetrics:
        """Calculate all evaluation metrics"""
        # Basic metrics
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)

        # ROC-AUC (only if we have both classes)
        try:
            if len(np.unique(y_true)) > 1:
                roc_auc = roc_auc_score(y_true, y_scores)
            else:
                roc_auc = 0.0
        except:
            roc_auc = 0.0

        # Confusion matrix
        try:
            tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
        except ValueError:
            # Handle edge cases where confusion matrix can't be computed
            tp = int(np.sum((y_true == 1) & (y_pred == 1)))
            tn = int(np.sum((y_true == 0) & (y_pred == 0)))
            fp = int(np.sum((y_true == 0) & (y_pred == 1)))
            fn = int(np.sum((y_true == 1) & (y_pred == 0)))

        # False positive rate
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        # Average detection latency
        avg_latency = np.mean(latencies) if latencies else 0.0

        return EvaluationMetrics(
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1),
            roc_auc=float(roc_auc),
            false_positive_rate=float(fpr),
            detection_latency_ms=float(avg_latency),
            total_samples=len(y_true),
            true_positives=int(tp),
            false_positives=int(fp),
            true_negatives=int(tn),
            false_negatives=int(fn)
        )

    def _empty_metrics(self) -> EvaluationMetrics:
        """Return empty metrics"""
        return EvaluationMetrics(
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            roc_auc=0.0,
            false_positive_rate=0.0,
            detection_latency_ms=0.0,
            total_samples=0,
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0
        )

    def save_results(self, metrics: EvaluationMetrics, name: str = "latest"):
        """Save evaluation results to file"""
        results = {
            "name": name,
            "timestamp": utc_isoformat(),
            "metrics": metrics.model_dump()
        }

        if self.results_path.exists():
            with open(self.results_path, 'r') as f:
                all_results = json.load(f)
        else:
            all_results = []

        all_results.append(results)
        all_results = all_results[-100:]  # Keep last 100

        with open(self.results_path, 'w') as f:
            json.dump(all_results, f, indent=2)

        print(f"Results saved to {self.results_path}")

    def load_results(self) -> List[Dict]:
        """Load historical evaluation results"""
        if not self.results_path.exists():
            return []

        with open(self.results_path, 'r') as f:
            return json.load(f)

    def print_report(self, metrics: EvaluationMetrics):
        """Print a formatted evaluation report"""
        print("\n" + "=" * 60)
        print("ANOMALY DETECTION EVALUATION REPORT")
        print("=" * 60)
        print(f"Timestamp: {utc_isoformat()}")
        print("-" * 60)

        print(f"\nSAMPLE STATISTICS:")
        print(f"  Total Samples:      {metrics.total_samples}")
        print(f"  True Positives:     {metrics.true_positives}")
        print(f"  False Positives:    {metrics.false_positives}")
        print(f"  True Negatives:     {metrics.true_negatives}")
        print(f"  False Negatives:    {metrics.false_negatives}")

        # Calculate and show class distribution
        total_attacks = metrics.true_positives + metrics.false_negatives
        total_normal = metrics.true_negatives + metrics.false_positives
        if metrics.total_samples > 0:
            attack_rate = total_attacks / metrics.total_samples * 100
            print(f"  Attack Rate:        {attack_rate:.1f}% ({total_attacks}/{metrics.total_samples})")

        print(f"\nPERFORMANCE METRICS:")
        print(f"  Precision:          {metrics.precision:.4f}")
        print(f"  Recall:             {metrics.recall:.4f}")
        print(f"  F1-Score:           {metrics.f1_score:.4f}")
        print(f"  ROC-AUC:            {metrics.roc_auc:.4f}")
        print(f"  False Positive Rate: {metrics.false_positive_rate:.4f}")

        print(f"\nLATENCY:")
        print(f"  Avg Detection Time: {metrics.detection_latency_ms:.2f} ms")

        print("\n" + "=" * 60)

        # Performance assessment with overfitting warning
        if metrics.f1_score == 1.0 and metrics.false_positives == 0 and metrics.false_negatives == 0:
            print("WARNING: Perfect scores may indicate overfitting!")
            print("         Consider using evaluate_with_holdout() with fresh test data.")
        elif metrics.f1_score >= 0.9:
            print("ASSESSMENT: Excellent detection performance")
            print("            (Verify with cross-validation to confirm)")
        elif metrics.f1_score >= 0.7:
            print("ASSESSMENT: Good detection performance")
        elif metrics.f1_score >= 0.5:
            print("ASSESSMENT: Moderate detection performance - consider tuning")
        else:
            print("ASSESSMENT: Poor detection performance - model needs improvement")

        print("=" * 60 + "\n")


# Singleton instance
evaluator = Evaluator()


def run_evaluation(mode: str = "holdout", **kwargs) -> EvaluationMetrics:
    """
    Run evaluation and print report.

    Args:
        mode: "holdout" (recommended), "elasticsearch_holdout", "cross_validation",
              "simulated" (deprecated), or "elasticsearch" (deprecated)
        **kwargs: Additional arguments for evaluation

    Returns:
        EvaluationMetrics
    """
    print(f"\nRunning {mode} evaluation...")

    if mode == "holdout":
        metrics = evaluator.evaluate_with_holdout(
            num_test_samples=kwargs.get('num_samples', 100),
            attack_ratio=kwargs.get('attack_ratio', 0.1),
            random_seed=kwargs.get('random_seed')
        )
    elif mode == "elasticsearch_holdout":
        metrics = evaluator.evaluate_from_elasticsearch_holdout(
            train_hours=kwargs.get('train_hours', 24),
            test_hours=kwargs.get('test_hours', 6),
            gap_hours=kwargs.get('gap_hours', 1),
            attack_ips=kwargs.get('attack_ips')
        )
    elif mode == "cross_validation":
        cv_results = evaluator.evaluate_with_cross_validation(
            num_folds=kwargs.get('num_folds', 5),
            num_samples=kwargs.get('num_samples', 200),
            attack_ratio=kwargs.get('attack_ratio', 0.15)
        )
        print(f"\nCross-Validation Results ({cv_results['num_folds']} folds):")
        print(f"  F1-Score:  {cv_results['f1_mean']:.3f} ± {cv_results['f1_std']:.3f}")
        print(f"  Precision: {cv_results['precision_mean']:.3f} ± {cv_results['precision_std']:.3f}")
        print(f"  Recall:    {cv_results['recall_mean']:.3f} ± {cv_results['recall_std']:.3f}")
        # Return the first fold metrics for compatibility
        return EvaluationMetrics(**cv_results['fold_metrics'][0])
    elif mode == "simulated":
        # Deprecated - redirects to holdout with 50/50
        metrics = evaluator.evaluate_with_simulated_data(
            num_samples=kwargs.get('num_samples', 100)
        )
    elif mode == "elasticsearch":
        # Deprecated
        metrics = evaluator.evaluate_from_elasticsearch(
            hours=kwargs.get('hours', 24),
            attack_ips=kwargs.get('attack_ips')
        )
    else:
        raise ValueError(f"Unknown evaluation mode: {mode}")

    evaluator.print_report(metrics)
    evaluator.save_results(metrics, name=mode)

    return metrics


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate Anomaly Detection Performance")
    parser.add_argument("--mode",
                        choices=["holdout", "elasticsearch_holdout", "cross_validation", "simulated", "elasticsearch"],
                        default="holdout",
                        help="Evaluation mode (holdout recommended)")
    parser.add_argument("--samples", type=int, default=100,
                        help="Number of samples for evaluation")
    parser.add_argument("--attack-ratio", type=float, default=0.1,
                        help="Proportion of attack samples (default 0.1 = 10%%)")
    parser.add_argument("--hours", type=int, default=24,
                        help="Hours of data for elasticsearch evaluation")
    parser.add_argument("--folds", type=int, default=5,
                        help="Number of folds for cross-validation")

    args = parser.parse_args()

    if args.mode == "holdout":
        run_evaluation("holdout", num_samples=args.samples, attack_ratio=args.attack_ratio)
    elif args.mode == "elasticsearch_holdout":
        run_evaluation("elasticsearch_holdout", train_hours=args.hours)
    elif args.mode == "cross_validation":
        run_evaluation("cross_validation", num_samples=args.samples, num_folds=args.folds, attack_ratio=args.attack_ratio)
    elif args.mode == "simulated":
        run_evaluation("simulated", num_samples=args.samples)
    else:
        run_evaluation("elasticsearch", hours=args.hours)
