"""
Overfitting Detection and Penalty Functions

Provides utilities to detect and quantify overfitting in backtests.

Functions:
- detect_overfitting: Binary overfitting detection
- compute_overfitting_penalty: Quantifies overfitting as penalty for fitness
- stability_score: Measures consistency across windows
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def detect_overfitting(
    train_metric: float,
    test_metric: float,
    threshold: float = 0.5,
    metric_name: str = "sharpe"
) -> bool:
    """
    Detect if a model is overfitting based on metric degradation.
    
    Args:
        train_metric: Metric value on training data
        test_metric: Metric value on test data
        threshold: Threshold for overfitting detection
        metric_name: Name of metric for logging
        
    Returns:
        True if overfitting detected (train >> test)
    """
    # For Sharpe, higher is better; overfitting if train much higher than test
    if metric_name.lower() in ["sharpe", "pnl", "return"]:
        degradation = train_metric - test_metric
        return degradation > threshold
    # For drawdown/loss, lower is better; overfitting if train much lower than test
    else:
        degradation = test_metric - train_metric
        return degradation > threshold


def compute_overfitting_penalty(
    train_metric: float,
    test_metric: float,
    tolerance: float = 0.3,
    penalty_scale: float = 1.0,
    metric_name: str = "sharpe"
) -> float:
    """
    Compute overfitting penalty for use in fitness functions.
    
    Penalty formula: max(0, (train - test - tolerance) * penalty_scale)
    
    Args:
        train_metric: Metric value on training data (e.g., Sharpe ratio)
        test_metric: Metric value on test data
        tolerance: Acceptable difference before penalty applies
        penalty_scale: Multiplier for penalty magnitude
        metric_name: Type of metric for context
        
    Returns:
        Penalty value (0 if within tolerance)
        
    Example:
        >>> compute_overfitting_penalty(1.5, 0.8, tolerance=0.3)
        0.4  # (1.5 - 0.8 - 0.3) * 1.0
    """
    if metric_name.lower() in ["sharpe", "pnl", "return"]:
        diff = train_metric - test_metric
    else:
        diff = test_metric - train_metric
    
    penalty = max(0.0, diff - tolerance) * penalty_scale
    return penalty


def stability_score(
    window_metrics: List[float],
    lookback: int = 5
) -> float:
    """
    Compute stability score (consistency of performance across windows).
    
    Higher score = more stable.
    
    Args:
        window_metrics: List of metrics from each window
        lookback: Number of recent windows to analyze
        
    Returns:
        Stability score between 0 and 1 (1.0 = perfectly stable)
    """
    if not window_metrics or len(window_metrics) < 2:
        return 0.5
    
    recent = window_metrics[-lookback:] if len(window_metrics) >= lookback else window_metrics
    
    # Stability = 1 - (std / mean), clipped to [0, 1]
    mean = np.mean(recent)
    if mean == 0:
        return 0.0
    
    std = np.std(recent)
    stability = 1.0 - (std / abs(mean))
    
    return max(0.0, min(1.0, stability))


def degradation_ratio(
    train_metrics: List[float],
    test_metrics: List[float]
) -> float:
    """
    Compute average degradation from train to test across all windows.
    
    Args:
        train_metrics: List of training metrics
        test_metrics: List of test metrics
        
    Returns:
        Average degradation ratio (0 = no degradation, >1 = severe degradation)
    """
    if not train_metrics or not test_metrics:
        return 0.0
    
    degradations = []
    for train, test in zip(train_metrics, test_metrics):
        if train != 0:
            ratio = abs(train - test) / abs(train)
            degradations.append(ratio)
    
    return np.mean(degradations) if degradations else 0.0


def is_robust_parameters(
    parameter_history: Dict[int, Dict[str, float]],
    tolerance_pct: float = 10.0
) -> bool:
    """
    Check if parameters remain stable (non-drifting) across windows.
    
    Args:
        parameter_history: Dict mapping window_id to {param_name: value}
        tolerance_pct: Percentage change threshold for drift detection
        
    Returns:
        True if parameters are stable across windows
    """
    if not parameter_history or len(parameter_history) < 2:
        return True
    
    window_ids = sorted(parameter_history.keys())
    param_names = set(parameter_history[window_ids[0]].keys())
    
    for param_name in param_names:
        values = [parameter_history[wid].get(param_name, 0) for wid in window_ids]
        
        # Skip constant parameters
        if all(v == values[0] for v in values):
            continue
        
        # Check max pct change between consecutive windows
        for i in range(len(values) - 1):
            if values[i] != 0:
                pct_change = abs(values[i + 1] - values[i]) / abs(values[i]) * 100
                if pct_change > tolerance_pct:
                    logger.warning(
                        f"Parameter {param_name} drifted {pct_change:.1f}% "
                        f"from window {i} ({values[i]}) to window {i+1} ({values[i+1]})"
                    )
                    return False
    
    return True


class OverfittingReport:
    """Generates detailed overfitting analysis report."""
    
    def __init__(self, walk_forward_validator: Any):
        """
        Initialize report from validator results.
        
        Args:
            walk_forward_validator: WalkForwardValidator with completed results
        """
        self.validator = walk_forward_validator
        self.results_df = self.validator.to_dataframe()
    
    def generate_text_report(self) -> str:
        """Generate human-readable text report."""
        lines = [
            "=" * 70,
            "WALK-FORWARD OVERFITTING ANALYSIS",
            "=" * 70,
            "",
        ]
        
        stats = self.validator.summary_statistics()
        
        lines.extend([
            "Summary Statistics:",
            f"  Windows Analyzed: {stats.get('num_windows', 0)}",
            f"  Avg Train Sharpe: {stats.get('avg_train_sharpe', 0):.3f}",
            f"  Avg Test Sharpe: {stats.get('avg_test_sharpe', 0):.3f}",
            f"  Min Test Sharpe: {stats.get('min_test_sharpe', 0):.3f}",
            f"  Max Test Sharpe: {stats.get('max_test_sharpe', 0):.3f}",
            f"  Avg Overfitting Penalty: {stats.get('avg_overfitting_penalty', 0):.3f}",
            f"  Max Overfitting Penalty: {stats.get('max_overfitting_penalty', 0):.3f}",
            f"  Out-of-Bounds Parameters: {stats.get('out_of_bounds_count', 0)}",
            "",
        ])
        
        # Degradation summary
        if not self.results_df.empty:
            avg_degradation = self.results_df['overfit_penalty'].mean()
            max_degradation = self.results_df['overfit_penalty'].max()
            
            lines.extend([
                "Degradation Analysis:",
                f"  Average Penalty: {avg_degradation:.3f}",
                f"  Maximum Penalty: {max_degradation:.3f}",
                "",
            ])
            
            # Warnings
            if avg_degradation > 0.5:
                lines.append("⚠️ WARNING: Significant overfitting detected!")
                lines.append(f"   Average test degradation is {avg_degradation:.1%}")
            
            if max_degradation > 1.0:
                lines.append("🔴 CRITICAL: Severe overfitting in at least one window!")
                lines.append(f"   Maximum degradation penalty: {max_degradation:.3f}")
        
        lines.extend(["", "=" * 70])
        return "\n".join(lines)
    
    def get_overfitting_severity(self) -> str:
        """
        Classify overfitting severity.
        
        Returns:
            "NONE", "LOW", "MODERATE", "HIGH", or "SEVERE"
        """
        stats = self.validator.summary_statistics()
        penalty = stats.get('max_overfitting_penalty', 0)
        
        if penalty < 0.1:
            return "NONE"
        elif penalty < 0.3:
            return "LOW"
        elif penalty < 0.7:
            return "MODERATE"
        elif penalty < 1.5:
            return "HIGH"
        else:
            return "SEVERE"
    
    def recommend_action(self) -> str:
        """
        Recommend action based on overfitting severity.
        
        Returns:
            Recommendation string
        """
        severity = self.get_overfitting_severity()
        
        if severity == "NONE":
            return "✅ Parameters show good generalization. Ready for deployment."
        elif severity == "LOW":
            return "✓ Acceptable overfitting. Consider monitoring performance."
        elif severity == "MODERATE":
            return "⚠️ Moderate overfitting detected. Consider adding regularization or constraints."
        elif severity == "HIGH":
            return "🔴 High overfitting. Recommend revising strategy or increasing training window."
        else:
            return "🚨 Severe overfitting. Strategy likely not generalizable. DO NOT DEPLOY."


def validate_walk_forward_results(results: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Validate walk-forward results for quality issues.
    
    Args:
        results: DataFrame from WalkForwardValidator.to_dataframe()
        
    Returns:
        (is_valid, list_of_issues)
    """
    issues = []
    
    if results.empty:
        issues.append("No results to validate")
        return False, issues
    
    # Check for excessive overfitting
    if results['overfit_penalty'].mean() > 1.0:
        issues.append(f"Average overfitting penalty {results['overfit_penalty'].mean():.3f} exceeds 1.0")
    
    # Check for NaN/inf values
    if results[['train_sharpe', 'test_sharpe']].isnull().any().any():
        issues.append("Found NaN values in metrics")
    
    # Check for negative test sharpe
    if (results['test_sharpe'] < -2.0).any():
        issues.append("Some test windows have very negative Sharpe ratios")
    
    # Check for inconsistent window sizes
    if 'window_duration' in results.columns:
        durations = results['window_duration'].unique()
        if len(durations) > 1:
            issues.append(f"Inconsistent window durations: {durations}")
    
    is_valid = len(issues) == 0
    return is_valid, issues


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test overfitting penalty calculation
    print("Testing overfitting penalty calculation:")
    
    test_cases = [
        (1.5, 1.4, 0.3, "Almost no overfitting"),
        (1.5, 0.8, 0.3, "Moderate overfitting"),
        (2.0, 0.0, 0.5, "Severe overfitting"),
    ]
    
    for train, test, tol, desc in test_cases:
        penalty = compute_overfitting_penalty(train, test, tolerance=tol)
        print(f"  {desc}: train={train}, test={test} → penalty={penalty:.3f}")
