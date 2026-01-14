"""
MODULE: Walk-Forward Validation Harness

Implements walk-forward analysis to detect overfitting and parameter drift.
Enables testing of parameters across overlapping train/test windows to measure
generalization performance and stability.

Features:
- Multiple window strategies: rolling, anchored (expanding), fixed-gap
- Drift detection: tracks parameter evolution across windows
- Overfitting detection: compares train vs test metrics
- Penalty functions: quantifies overfitting impact on fitness
- Config-driven: all parameters tunable via walk_forward.yaml

Usage:
    from backtests.walk_forward import WalkForwardValidator, WindowStrategy
    
    validator = WalkForwardValidator(
        data=df,
        strategy_class=MyStrategy,
        initial_params={"ema_fast": 12, "ema_slow": 26},
        window_strategy=WindowStrategy.ROLLING,
        train_window_days=30,
        test_window_days=7,
        overlap_days=0
    )
    
    results = validator.run()
    overfitting_penalty = validator.compute_overfitting_penalty(
        train_sharpe=1.5,
        test_sharpe=0.8,
        tolerance=0.3
    )
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class WindowStrategy(Enum):
    """Window splitting strategy for walk-forward analysis."""
    ROLLING = "rolling"          # Sliding window, no overlap
    ANCHORED = "anchored"        # Expanding window (fixed start)
    FIXED_GAP = "fixed_gap"      # Fixed window with gap between train/test


class WalkForwardWindow:
    """Single train/test window pair."""
    
    def __init__(
        self,
        window_id: int,
        train_start: datetime,
        train_end: datetime,
        test_start: datetime,
        test_end: datetime
    ):
        """
        Initialize a walk-forward window.
        
        Args:
            window_id: Window number (0-indexed)
            train_start: Training period start (inclusive)
            train_end: Training period end (exclusive)
            test_start: Test period start (inclusive)
            test_end: Test period end (exclusive)
        """
        self.window_id = window_id
        self.train_start = train_start
        self.train_end = train_end
        self.test_start = test_start
        self.test_end = test_end
        
    def train_duration_days(self) -> float:
        """Duration of training period in days."""
        return (self.train_end - self.train_start).days
    
    def test_duration_days(self) -> float:
        """Duration of test period in days."""
        return (self.test_end - self.test_start).days
    
    def gap_days(self) -> float:
        """Gap between train and test periods in days."""
        return (self.test_start - self.train_end).days


class WindowGenerator:
    """Generates train/test window splits."""
    
    @staticmethod
    def rolling_windows(
        data: pd.DataFrame,
        train_window_days: int,
        test_window_days: int,
        step_days: int = None
    ) -> List[WalkForwardWindow]:
        """
        Generate rolling windows (sliding window, no overlap).
        
        Args:
            data: OHLCV data with timestamp index
            train_window_days: Days for training window
            test_window_days: Days for test window
            step_days: Days to slide window (default: test_window_days)
            
        Returns:
            List of WalkForwardWindow objects
        """
        if step_days is None:
            step_days = test_window_days
        
        if data.empty:
            return []
        
        data_sorted = data.sort_index()
        date_index = pd.to_datetime(data_sorted.index) if not isinstance(data_sorted.index, pd.DatetimeIndex) else data_sorted.index
        
        start_date = date_index[0].to_pydatetime()
        end_date = date_index[-1].to_pydatetime()
        
        windows = []
        window_id = 0
        current_train_start = start_date
        
        while current_train_start + timedelta(days=train_window_days + test_window_days) <= end_date:
            train_end = current_train_start + timedelta(days=train_window_days)
            test_end = train_end + timedelta(days=test_window_days)
            
            window = WalkForwardWindow(
                window_id=window_id,
                train_start=current_train_start,
                train_end=train_end,
                test_start=train_end,
                test_end=test_end
            )
            windows.append(window)
            
            current_train_start += timedelta(days=step_days)
            window_id += 1
        
        return windows
    
    @staticmethod
    def anchored_windows(
        data: pd.DataFrame,
        train_window_days: int,
        test_window_days: int,
        step_days: int = None
    ) -> List[WalkForwardWindow]:
        """
        Generate anchored (expanding) windows.
        
        Args:
            data: OHLCV data with timestamp index
            train_window_days: Initial training window days
            test_window_days: Days for each test window
            step_days: Days to slide test window (default: test_window_days)
            
        Returns:
            List of WalkForwardWindow objects
        """
        if step_days is None:
            step_days = test_window_days
        
        if data.empty:
            return []
        
        data_sorted = data.sort_index()
        date_index = pd.to_datetime(data_sorted.index) if not isinstance(data_sorted.index, pd.DatetimeIndex) else data_sorted.index
        
        start_date = date_index[0].to_pydatetime()
        end_date = date_index[-1].to_pydatetime()
        
        windows = []
        window_id = 0
        initial_train_end = start_date + timedelta(days=train_window_days)
        current_test_start = initial_train_end
        
        while current_test_start + timedelta(days=test_window_days) <= end_date:
            test_end = current_test_start + timedelta(days=test_window_days)
            
            window = WalkForwardWindow(
                window_id=window_id,
                train_start=start_date,
                train_end=current_test_start,
                test_start=current_test_start,
                test_end=test_end
            )
            windows.append(window)
            
            current_test_start += timedelta(days=step_days)
            window_id += 1
        
        return windows
    
    @staticmethod
    def fixed_gap_windows(
        data: pd.DataFrame,
        train_window_days: int,
        test_window_days: int,
        gap_days: int = 1,
        step_days: int = None
    ) -> List[WalkForwardWindow]:
        """
        Generate windows with fixed gap between train and test.
        
        Args:
            data: OHLCV data with timestamp index
            train_window_days: Days for training window
            test_window_days: Days for test window
            gap_days: Days of gap between train and test
            step_days: Days to slide window (default: test_window_days)
            
        Returns:
            List of WalkForwardWindow objects
        """
        if step_days is None:
            step_days = test_window_days
        
        if data.empty:
            return []
        
        data_sorted = data.sort_index()
        date_index = pd.to_datetime(data_sorted.index) if not isinstance(data_sorted.index, pd.DatetimeIndex) else data_sorted.index
        
        start_date = date_index[0].to_pydatetime()
        end_date = date_index[-1].to_pydatetime()
        
        windows = []
        window_id = 0
        current_train_start = start_date
        
        total_window = train_window_days + gap_days + test_window_days
        while current_train_start + timedelta(days=total_window) <= end_date:
            train_end = current_train_start + timedelta(days=train_window_days)
            test_start = train_end + timedelta(days=gap_days)
            test_end = test_start + timedelta(days=test_window_days)
            
            window = WalkForwardWindow(
                window_id=window_id,
                train_start=current_train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end
            )
            windows.append(window)
            
            current_train_start += timedelta(days=step_days)
            window_id += 1
        
        return windows


class DriftMonitor:
    """Monitors parameter drift across windows."""
    
    def __init__(self, parameter_bounds: Dict[str, Tuple[float, float]] = None):
        """
        Initialize drift monitor.
        
        Args:
            parameter_bounds: Dict of {param_name: (min, max)} for bounds checking
        """
        self.parameter_bounds = parameter_bounds or {}
        self.parameter_history: Dict[int, Dict[str, float]] = {}
    
    def record_parameters(self, window_id: int, params: Dict[str, Any]):
        """Record parameters for a window."""
        self.parameter_history[window_id] = dict(params)
    
    def compute_drift(self, param_name: str, window_id: int) -> Optional[float]:
        """
        Compute drift for a parameter between current and previous window.
        
        Returns:
            Absolute change from previous window, or None if no previous window
        """
        if window_id == 0 or param_name not in self.parameter_history[window_id]:
            return None
        
        current_val = self.parameter_history[window_id][param_name]
        prev_val = self.parameter_history[window_id - 1].get(param_name)
        
        if prev_val is None:
            return None
        
        return abs(current_val - prev_val)
    
    def drift_penalty(
        self,
        window_id: int,
        max_drift_per_generation: float = 5.0
    ) -> float:
        """
        Compute penalty for parameter drift in this window.
        
        Args:
            window_id: Window ID
            max_drift_per_generation: Acceptable drift threshold
            
        Returns:
            Penalty value (0 if no drift, higher if excessive drift)
        """
        if window_id == 0:
            return 0.0
        
        total_drift = 0.0
        param_count = 0
        
        current_params = self.parameter_history.get(window_id, {})
        for param_name in current_params:
            drift = self.compute_drift(param_name, window_id)
            if drift is not None:
                total_drift += drift
                param_count += 1
        
        if param_count == 0:
            return 0.0
        
        avg_drift = total_drift / param_count
        if avg_drift > max_drift_per_generation:
            return (avg_drift - max_drift_per_generation) * 0.1
        
        return 0.0
    
    def out_of_bounds_count(self, window_id: int) -> int:
        """Count how many parameters are outside bounds in a window."""
        if window_id not in self.parameter_history:
            return 0
        
        count = 0
        params = self.parameter_history[window_id]
        for param_name, value in params.items():
            if param_name in self.parameter_bounds:
                min_val, max_val = self.parameter_bounds[param_name]
                if not (min_val <= value <= max_val):
                    count += 1
        
        return count


class WalkForwardValidator:
    """Orchestrates walk-forward analysis."""
    
    def __init__(
        self,
        data: pd.DataFrame,
        window_strategy: WindowStrategy = WindowStrategy.ROLLING,
        train_window_days: int = 30,
        test_window_days: int = 7,
        overlap_days: int = 0,
        parameter_bounds: Dict[str, Tuple[float, float]] = None,
        gap_days: int = 1
    ):
        """
        Initialize walk-forward validator.
        
        Args:
            data: Historical OHLCV data with timestamp index
            window_strategy: Strategy for window generation (ROLLING, ANCHORED, FIXED_GAP)
            train_window_days: Days for training window
            test_window_days: Days for test window
            overlap_days: Overlap between windows (for rolling strategy)
            parameter_bounds: Dict of parameter bounds for drift checking
            gap_days: Gap between train/test (for FIXED_GAP strategy)
        """
        self.data = data
        self.window_strategy = window_strategy
        self.train_window_days = train_window_days
        self.test_window_days = test_window_days
        self.overlap_days = overlap_days
        self.gap_days = gap_days
        
        self.windows: List[WalkForwardWindow] = []
        self.drift_monitor = DriftMonitor(parameter_bounds)
        self.results: Dict[int, Dict[str, Any]] = {}
        
        self._generate_windows()
    
    def _generate_windows(self):
        """Generate window splits based on strategy."""
        step_days = max(1, self.test_window_days - self.overlap_days)
        
        if self.window_strategy == WindowStrategy.ROLLING:
            self.windows = WindowGenerator.rolling_windows(
                self.data,
                self.train_window_days,
                self.test_window_days,
                step_days
            )
        elif self.window_strategy == WindowStrategy.ANCHORED:
            self.windows = WindowGenerator.anchored_windows(
                self.data,
                self.train_window_days,
                self.test_window_days,
                step_days
            )
        elif self.window_strategy == WindowStrategy.FIXED_GAP:
            self.windows = WindowGenerator.fixed_gap_windows(
                self.data,
                self.train_window_days,
                self.test_window_days,
                self.gap_days,
                step_days
            )
        
        logger.info(f"Generated {len(self.windows)} walk-forward windows")
    
    def get_window_data(
        self,
        window: WalkForwardWindow,
        split: str = "train"
    ) -> pd.DataFrame:
        """
        Extract data for a window.
        
        Args:
            window: WalkForwardWindow object
            split: "train" or "test"
            
        Returns:
            Filtered DataFrame for the window
        """
        if split == "train":
            start, end = window.train_start, window.train_end
        elif split == "test":
            start, end = window.test_start, window.test_end
        else:
            raise ValueError(f"Invalid split: {split}")
        
        data_sorted = self.data.sort_index()
        date_index = pd.to_datetime(data_sorted.index) if not isinstance(data_sorted.index, pd.DatetimeIndex) else data_sorted.index
        
        mask = (date_index >= start) & (date_index < end)
        return data_sorted[mask]
    
    def record_window_result(
        self,
        window_id: int,
        params: Dict[str, Any],
        train_metrics: Dict[str, float],
        test_metrics: Dict[str, float]
    ):
        """
        Record results for a window.
        
        Args:
            window_id: Window number
            params: Parameters used in this window
            train_metrics: Metrics from training period (e.g., sharpe, pnl)
            test_metrics: Metrics from test period
        """
        self.drift_monitor.record_parameters(window_id, params)
        
        self.results[window_id] = {
            "params": dict(params),
            "train_metrics": dict(train_metrics),
            "test_metrics": dict(test_metrics),
            "drift": self.drift_monitor.compute_drift("ema_fast", window_id) if "ema_fast" in params else None
        }
    
    @staticmethod
    def compute_overfitting_penalty(
        train_sharpe: float,
        test_sharpe: float,
        tolerance: float = 0.3
    ) -> float:
        """
        Compute overfitting penalty as (train_sharpe - test_sharpe - tolerance).
        
        Args:
            train_sharpe: Sharpe ratio on training data
            test_sharpe: Sharpe ratio on test data
            tolerance: Acceptable difference threshold
            
        Returns:
            Penalty value (0 if within tolerance, positive if overfitted)
        """
        diff = train_sharpe - test_sharpe
        penalty = max(0.0, diff - tolerance)
        return penalty
    
    def summary_statistics(self) -> Dict[str, Any]:
        """
        Compute summary statistics across all windows.
        
        Returns:
            Dictionary with avg/min/max metrics
        """
        if not self.results:
            return {}
        
        train_sharpes = []
        test_sharpes = []
        overfit_penalties = []
        
        for result in self.results.values():
            train_sharpe = result["train_metrics"].get("sharpe", 0)
            test_sharpe = result["test_metrics"].get("sharpe", 0)
            
            train_sharpes.append(train_sharpe)
            test_sharpes.append(test_sharpe)
            
            penalty = self.compute_overfitting_penalty(train_sharpe, test_sharpe)
            overfit_penalties.append(penalty)
        
        return {
            "num_windows": len(self.results),
            "avg_train_sharpe": np.mean(train_sharpes) if train_sharpes else 0,
            "avg_test_sharpe": np.mean(test_sharpes) if test_sharpes else 0,
            "min_test_sharpe": np.min(test_sharpes) if test_sharpes else 0,
            "max_test_sharpe": np.max(test_sharpes) if test_sharpes else 0,
            "avg_overfitting_penalty": np.mean(overfit_penalties) if overfit_penalties else 0,
            "max_overfitting_penalty": np.max(overfit_penalties) if overfit_penalties else 0,
            "out_of_bounds_count": self.drift_monitor.out_of_bounds_count(len(self.results) - 1)
        }
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert results to DataFrame for analysis.
        
        Returns:
            DataFrame with columns: window_id, train_sharpe, test_sharpe, overfit_penalty, ...
        """
        rows = []
        for window_id, result in self.results.items():
            train_sharpe = result["train_metrics"].get("sharpe", 0)
            test_sharpe = result["test_metrics"].get("sharpe", 0)
            penalty = self.compute_overfitting_penalty(train_sharpe, test_sharpe)
            
            row = {
                "window_id": window_id,
                "train_sharpe": train_sharpe,
                "test_sharpe": test_sharpe,
                "overfit_penalty": penalty,
                "drift": result.get("drift", 0),
            }
            rows.append(row)
        
        return pd.DataFrame(rows)


def create_walk_forward_from_config(config: Dict[str, Any]) -> WalkForwardValidator:
    """
    Factory function to create WalkForwardValidator from config dict.
    
    Args:
        config: Config with keys: strategy, data, window_strategy, train_days, test_days, etc.
        
    Returns:
        WalkForwardValidator instance
    """
    data = config.get("data")
    if data is None:
        raise ValueError("Config must contain 'data' key")
    
    window_strategy_str = config.get("window_strategy", "rolling").upper()
    window_strategy = WindowStrategy[window_strategy_str]
    
    parameter_bounds = config.get("parameter_bounds")
    
    return WalkForwardValidator(
        data=data,
        window_strategy=window_strategy,
        train_window_days=config.get("train_window_days", 30),
        test_window_days=config.get("test_window_days", 7),
        overlap_days=config.get("overlap_days", 0),
        parameter_bounds=parameter_bounds,
        gap_days=config.get("gap_days", 1)
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Walk-Forward Validation Module loaded successfully")
    print(f"Strategies: {[s.value for s in WindowStrategy]}")
    print(f"Classes: WalkForwardValidator, DriftMonitor, WindowGenerator, WindowStrategy")
