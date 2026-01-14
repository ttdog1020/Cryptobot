"""
Unit tests for walk-forward validation harness.

Tests:
- Window generation strategies (rolling, anchored, fixed-gap)
- Drift detection and monitoring
- Overfitting penalty computation
- Parameter bounds checking
- Integration with backtests
"""

import pytest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtests.walk_forward import (
    WalkForwardValidator, WalkForwardWindow, WindowGenerator, WindowStrategy,
    DriftMonitor, create_walk_forward_from_config
)
from validation.overfitting_check import (
    compute_overfitting_penalty, detect_overfitting, stability_score,
    degradation_ratio, is_robust_parameters, validate_walk_forward_results
)


class TestWalkForwardWindow:
    """Tests for WalkForwardWindow class."""
    
    def test_window_initialization(self):
        """Test window creation with valid dates."""
        start = datetime(2025, 1, 1)
        train_end = datetime(2025, 1, 31)
        test_start = datetime(2025, 1, 31)
        test_end = datetime(2025, 2, 7)
        
        window = WalkForwardWindow(0, start, train_end, test_start, test_end)
        
        assert window.window_id == 0
        assert window.train_start == start
        assert window.train_duration_days() == 30
        assert window.test_duration_days() == 7
    
    def test_gap_calculation(self):
        """Test gap calculation between train and test."""
        start = datetime(2025, 1, 1)
        train_end = datetime(2025, 1, 31)
        test_start = datetime(2025, 2, 7)  # 7 day gap
        test_end = datetime(2025, 2, 14)
        
        window = WalkForwardWindow(0, start, train_end, test_start, test_end)
        
        assert window.gap_days() == 7


class TestWindowGenerator:
    """Tests for window generation strategies."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data."""
        dates = pd.date_range('2025-01-01', periods=365, freq='D')
        data = pd.DataFrame({
            'open': np.random.randn(365).cumsum() + 100,
            'high': np.random.randn(365).cumsum() + 102,
            'low': np.random.randn(365).cumsum() + 98,
            'close': np.random.randn(365).cumsum() + 100,
            'volume': np.random.randint(1000, 10000, 365)
        }, index=dates)
        return data
    
    def test_rolling_windows(self, sample_data):
        """Test rolling window generation."""
        windows = WindowGenerator.rolling_windows(
            sample_data,
            train_window_days=30,
            test_window_days=7,
            step_days=7
        )
        
        assert len(windows) > 0
        assert all(w.window_id == i for i, w in enumerate(windows))
        assert all(w.train_duration_days() == 30 for w in windows)
        assert all(w.test_duration_days() == 7 for w in windows)
        assert all(w.gap_days() == 0 for w in windows)
    
    def test_anchored_windows(self, sample_data):
        """Test anchored (expanding) window generation."""
        windows = WindowGenerator.anchored_windows(
            sample_data,
            train_window_days=30,
            test_window_days=7,
            step_days=7
        )
        
        assert len(windows) > 0
        # Each window should have same train start
        train_starts = [w.train_start for w in windows]
        assert all(s == train_starts[0] for s in train_starts)
        # Train window should expand
        train_durations = [w.train_duration_days() for w in windows]
        assert train_durations == sorted(train_durations)
    
    def test_fixed_gap_windows(self, sample_data):
        """Test fixed-gap window generation."""
        windows = WindowGenerator.fixed_gap_windows(
            sample_data,
            train_window_days=30,
            test_window_days=7,
            gap_days=3,
            step_days=7
        )
        
        assert len(windows) > 0
        assert all(w.gap_days() == 3 for w in windows)
    
    def test_empty_data(self):
        """Test window generation with empty data."""
        empty_df = pd.DataFrame()
        
        windows = WindowGenerator.rolling_windows(empty_df, 30, 7)
        assert windows == []


class TestDriftMonitor:
    """Tests for parameter drift monitoring."""
    
    def test_drift_recording(self):
        """Test parameter recording across windows."""
        monitor = DriftMonitor()
        
        params_window_0 = {"ema_fast": 12, "ema_slow": 26}
        params_window_1 = {"ema_fast": 13, "ema_slow": 27}
        
        monitor.record_parameters(0, params_window_0)
        monitor.record_parameters(1, params_window_1)
        
        assert monitor.parameter_history[0] == params_window_0
        assert monitor.parameter_history[1] == params_window_1
    
    def test_drift_calculation(self):
        """Test drift computation between windows."""
        monitor = DriftMonitor()
        
        monitor.record_parameters(0, {"ema_fast": 12})
        monitor.record_parameters(1, {"ema_fast": 14})
        
        drift = monitor.compute_drift("ema_fast", 1)
        assert drift == 2.0
    
    def test_bounds_checking(self):
        """Test parameter bounds violation detection."""
        bounds = {"ema_fast": (5, 20), "ema_slow": (20, 50)}
        monitor = DriftMonitor(bounds)
        
        # Valid parameters
        monitor.record_parameters(0, {"ema_fast": 12, "ema_slow": 26})
        assert monitor.out_of_bounds_count(0) == 0
        
        # Invalid parameters
        monitor.record_parameters(1, {"ema_fast": 22, "ema_slow": 26})
        assert monitor.out_of_bounds_count(1) == 1
    
    def test_drift_penalty(self):
        """Test drift penalty calculation."""
        monitor = DriftMonitor()
        
        monitor.record_parameters(0, {"ema_fast": 12, "ema_slow": 26})
        monitor.record_parameters(1, {"ema_fast": 12, "ema_slow": 26})
        
        # No drift = no penalty
        penalty = monitor.drift_penalty(1, max_drift_per_generation=5.0)
        assert penalty == 0.0


class TestWalkForwardValidator:
    """Tests for main validator class."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        dates = pd.date_range('2025-01-01', periods=180, freq='D')
        data = pd.DataFrame({
            'close': np.random.randn(180).cumsum() + 100,
            'volume': np.random.randint(1000, 10000, 180)
        }, index=dates)
        return data
    
    def test_validator_initialization(self, sample_data):
        """Test validator initialization."""
        validator = WalkForwardValidator(
            sample_data,
            window_strategy=WindowStrategy.ROLLING,
            train_window_days=30,
            test_window_days=7
        )
        
        assert validator.window_strategy == WindowStrategy.ROLLING
        assert len(validator.windows) > 0
    
    def test_window_data_extraction(self, sample_data):
        """Test extracting data for a window."""
        validator = WalkForwardValidator(
            sample_data,
            window_strategy=WindowStrategy.ROLLING,
            train_window_days=30,
            test_window_days=7
        )
        
        if validator.windows:
            window = validator.windows[0]
            train_data = validator.get_window_data(window, split="train")
            test_data = validator.get_window_data(window, split="test")
            
            assert not train_data.empty
            assert not test_data.empty
            assert len(train_data) > 0
            assert len(test_data) > 0
    
    def test_result_recording(self, sample_data):
        """Test recording window results."""
        validator = WalkForwardValidator(sample_data)
        
        params = {"ema_fast": 12, "ema_slow": 26}
        train_metrics = {"sharpe": 1.5, "pnl": 1000}
        test_metrics = {"sharpe": 0.8, "pnl": 500}
        
        validator.record_window_result(0, params, train_metrics, test_metrics)
        
        assert 0 in validator.results
        assert validator.results[0]["params"] == params
    
    def test_overfitting_penalty_computation(self):
        """Test overfitting penalty calculation."""
        penalty = WalkForwardValidator.compute_overfitting_penalty(
            train_sharpe=1.5,
            test_sharpe=0.8,
            tolerance=0.3
        )
        
        # (1.5 - 0.8 - 0.3) = 0.4
        assert penalty == pytest.approx(0.4, abs=0.01)
    
    def test_summary_statistics(self, sample_data):
        """Test summary statistics generation."""
        validator = WalkForwardValidator(sample_data, train_window_days=20, test_window_days=5)
        
        # Add sample results
        for window_id in range(min(3, len(validator.windows))):
            validator.record_window_result(
                window_id,
                {"ema_fast": 12 + window_id},
                {"sharpe": 1.0 + window_id * 0.1},
                {"sharpe": 0.8 + window_id * 0.05}
            )
        
        stats = validator.summary_statistics()
        
        assert "num_windows" in stats
        assert stats["num_windows"] > 0


class TestOverfittingDetection:
    """Tests for overfitting detection functions."""
    
    def test_overfitting_penalty(self):
        """Test overfitting penalty computation."""
        # No overfitting
        penalty = compute_overfitting_penalty(1.0, 1.0, tolerance=0.3)
        assert penalty == 0.0
        
        # Some overfitting within tolerance
        penalty = compute_overfitting_penalty(1.2, 1.0, tolerance=0.3)
        assert penalty == 0.0
        
        # Overfitting exceeds tolerance
        penalty = compute_overfitting_penalty(1.5, 0.8, tolerance=0.3)
        assert penalty > 0.0
    
    def test_detect_overfitting(self):
        """Test overfitting detection."""
        # No overfitting
        assert not detect_overfitting(1.0, 1.0, threshold=0.5)
        
        # Slight overfitting
        assert not detect_overfitting(1.2, 1.0, threshold=0.5)
        
        # Severe overfitting
        assert detect_overfitting(1.5, 0.5, threshold=0.5)
    
    def test_stability_score(self):
        """Test stability score calculation."""
        # Stable metrics
        metrics = [1.0, 1.0, 1.0]
        score = stability_score(metrics)
        assert score > 0.9
        
        # Volatile metrics
        metrics = [1.0, 0.1, 2.0]
        score = stability_score(metrics)
        assert score < 0.8
    
    def test_degradation_ratio(self):
        """Test degradation ratio."""
        train_metrics = [1.5, 1.4, 1.6]
        test_metrics = [1.0, 1.0, 1.0]
        
        ratio = degradation_ratio(train_metrics, test_metrics)
        assert 0 < ratio < 1.0
    
    def test_robust_parameters(self):
        """Test parameter stability checking."""
        # Stable parameters
        params = {
            0: {"ema_fast": 12, "ema_slow": 26},
            1: {"ema_fast": 12, "ema_slow": 26},
            2: {"ema_fast": 12, "ema_slow": 26},
        }
        assert is_robust_parameters(params, tolerance_pct=10)
        
        # Drifting parameters
        params = {
            0: {"ema_fast": 12},
            1: {"ema_fast": 18},  # 50% change
        }
        assert not is_robust_parameters(params, tolerance_pct=10)


class TestCreateFromConfig:
    """Tests for config factory."""
    
    def test_create_from_config(self):
        """Test validator creation from config dict."""
        dates = pd.date_range('2025-01-01', periods=100, freq='D')
        data = pd.DataFrame({
            'close': np.random.randn(100).cumsum() + 100
        }, index=dates)
        
        config = {
            "data": data,
            "window_strategy": "rolling",
            "train_window_days": 20,
            "test_window_days": 5,
        }
        
        validator = create_walk_forward_from_config(config)
        assert isinstance(validator, WalkForwardValidator)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
