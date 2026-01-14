"""
MODULE 30: Tests for Parameter Search Optimizer

Tests for optimizer.param_search module including:
- Parameter grid iteration
- Config override creation
- Backtest execution
- Metric computation
- Full optimization run
"""

import unittest
import tempfile
import yaml
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from optimizer.param_search import (
    OptimizationRunConfig,
    iter_param_combinations,
    run_param_search,
    _create_temp_config,
    _compute_metrics_from_log
)


class TestParamCombinations(unittest.TestCase):
    """Test parameter grid iteration."""
    
    def test_empty_grid(self):
        """Test empty parameter grid."""
        grid = {}
        combos = list(iter_param_combinations(grid))
        self.assertEqual(len(combos), 1)
        self.assertEqual(combos[0], {})
    
    def test_single_param(self):
        """Test single parameter with multiple values."""
        grid = {"fast": [5, 8, 12]}
        combos = list(iter_param_combinations(grid))
        self.assertEqual(len(combos), 3)
        self.assertEqual(combos[0], {"fast": 5})
        self.assertEqual(combos[1], {"fast": 8})
        self.assertEqual(combos[2], {"fast": 12})
    
    def test_multiple_params(self):
        """Test Cartesian product of multiple parameters."""
        grid = {
            "fast": [5, 8],
            "slow": [21, 26]
        }
        combos = list(iter_param_combinations(grid))
        self.assertEqual(len(combos), 4)
        
        # Check all combinations present
        expected = [
            {"fast": 5, "slow": 21},
            {"fast": 5, "slow": 26},
            {"fast": 8, "slow": 21},
            {"fast": 8, "slow": 26}
        ]
        self.assertEqual(combos, expected)
    
    def test_three_params(self):
        """Test three parameters."""
        grid = {
            "fast": [5, 8],
            "slow": [21],
            "rsi": [70, 75]
        }
        combos = list(iter_param_combinations(grid))
        self.assertEqual(len(combos), 4)  # 2 * 1 * 2


class TestTempConfig(unittest.TestCase):
    """Test temporary config file creation."""
    
    def setUp(self):
        """Create temporary base config."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_config_path = Path(self.temp_dir) / "base.yaml"
        
        # Create base config
        base_config = {
            "exchange": "binance_us",
            "symbols": ["BTCUSDT"],
            "timeframe": "1m",
            "strategy": {
                "type": "scalping_ema_rsi",
                "params": {
                    "ema_fast": 5,
                    "ema_slow": 9
                }
            }
        }
        
        with open(self.base_config_path, 'w') as f:
            yaml.dump(base_config, f)
    
    def test_create_temp_config(self):
        """Test creating temporary config with overrides."""
        overrides = {
            "ema_fast": 12,
            "rsi_overbought": 75
        }
        
        temp_path = _create_temp_config(str(self.base_config_path), overrides)
        
        # Verify temp file exists
        self.assertTrue(temp_path.exists())
        
        # Load and verify content
        with open(temp_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check overrides applied
        self.assertEqual(config["strategy"]["params"]["ema_fast"], 12)
        self.assertEqual(config["strategy"]["params"]["rsi_overbought"], 75)
        
        # Check original values preserved
        self.assertEqual(config["strategy"]["params"]["ema_slow"], 9)
        self.assertEqual(config["exchange"], "binance_us")
        
        # Cleanup
        temp_path.unlink()
    
    def test_create_temp_config_no_strategy_section(self):
        """Test creating temp config when base has no strategy section."""
        # Create minimal base config
        minimal_config = {"exchange": "binance_us"}
        minimal_path = Path(self.temp_dir) / "minimal.yaml"
        with open(minimal_path, 'w') as f:
            yaml.dump(minimal_config, f)
        
        overrides = {"ema_fast": 8}
        temp_path = _create_temp_config(str(minimal_path), overrides)
        
        # Verify strategy section created
        with open(temp_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.assertIn("strategy", config)
        self.assertIn("params", config["strategy"])
        self.assertEqual(config["strategy"]["params"]["ema_fast"], 8)
        
        # Cleanup
        temp_path.unlink()


class TestOptimizationConfig(unittest.TestCase):
    """Test OptimizationRunConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = OptimizationRunConfig(
            symbols=["BTCUSDT"],
            start=datetime(2025, 11, 1),
            end=datetime(2025, 12, 1)
        )
        
        self.assertEqual(config.interval, "1m")
        self.assertEqual(config.param_grid, {})
        self.assertIsNone(config.max_runs)
        self.assertEqual(config.label, "scalping_ema_rsi_opt")
        self.assertEqual(config.base_config_path, "config/live.yaml")
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = OptimizationRunConfig(
            symbols=["BTCUSDT", "ETHUSDT"],
            start=datetime(2025, 11, 1),
            end=datetime(2025, 12, 1),
            interval="5m",
            param_grid={"fast": [5, 8]},
            max_runs=10,
            label="my_opt"
        )
        
        self.assertEqual(config.symbols, ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(config.interval, "5m")
        self.assertEqual(config.param_grid, {"fast": [5, 8]})
        self.assertEqual(config.max_runs, 10)
        self.assertEqual(config.label, "my_opt")


class TestParamSearchIntegration(unittest.TestCase):
    """Integration tests for parameter search (using small grids)."""
    
    @patch('optimizer.param_search.run_config_backtest')
    @patch('optimizer.param_search.PaperTradeReport')
    def test_run_param_search_mock(self, mock_report_class, mock_backtest):
        """Test parameter search with mocked backtest."""
        # Setup mocks
        mock_backtest.return_value = Path("logs/test.csv")
        
        # Mock metrics
        mock_report = MagicMock()
        mock_report.get_overall_metrics.return_value = {
            'total_pnl_pct': 5.0,
            'total_pnl': 500.0,
            'total_trades': 10,
            'win_rate': 60.0,
            'max_drawdown_pct': 2.0,
            'avg_trade_pnl': 50.0,
            'largest_win': 100.0,
            'largest_loss': -50.0
        }
        mock_report_class.return_value = mock_report
        
        # Create config with small grid (2 combinations)
        config = OptimizationRunConfig(
            symbols=["BTCUSDT"],
            start=datetime(2025, 12, 1),
            end=datetime(2025, 12, 2),
            interval="1m",
            param_grid={"fast": [5, 8]},
            label="test_opt"
        )
        
        # Run search
        results = run_param_search(config)
        
        # Verify results
        self.assertEqual(len(results), 2)
        
        # Check first result structure
        self.assertIn('params', results[0])
        self.assertIn('score', results[0])
        self.assertIn('metrics', results[0])
        self.assertIn('symbols', results[0])
        
        # Check results sorted by score
        self.assertGreaterEqual(results[0]['score'], results[1]['score'])
        
        # Verify backtest called twice
        self.assertEqual(mock_backtest.call_count, 2)
    
    @patch('optimizer.param_search.run_config_backtest')
    @patch('optimizer.param_search.PaperTradeReport')
    def test_run_param_search_with_max_runs(self, mock_report_class, mock_backtest):
        """Test max_runs limit."""
        # Setup mocks
        mock_backtest.return_value = Path("logs/test.csv")
        mock_report = MagicMock()
        mock_report.get_overall_metrics.return_value = {
            'total_pnl_pct': 5.0,
            'total_pnl': 500.0,
            'total_trades': 10,
            'win_rate': 60.0,
            'max_drawdown_pct': 2.0,
            'avg_trade_pnl': 50.0,
            'largest_win': 100.0,
            'largest_loss': -50.0
        }
        mock_report_class.return_value = mock_report
        
        # Create config with grid of 4 combinations but max_runs=2
        config = OptimizationRunConfig(
            symbols=["BTCUSDT"],
            start=datetime(2025, 12, 1),
            end=datetime(2025, 12, 2),
            param_grid={"fast": [5, 8], "slow": [21, 26]},  # 4 combos
            max_runs=2,
            label="test_max_runs"
        )
        
        # Run search
        results = run_param_search(config)
        
        # Verify only 2 runs executed
        self.assertEqual(len(results), 2)
        self.assertEqual(mock_backtest.call_count, 2)
    
    @patch('optimizer.param_search.run_config_backtest')
    @patch('optimizer.param_search.PaperTradeReport')
    def test_run_param_search_handles_errors(self, mock_report_class, mock_backtest):
        """Test error handling in parameter search."""
        # Make backtest raise an exception
        mock_backtest.side_effect = Exception("Backtest failed")
        
        # Create config
        config = OptimizationRunConfig(
            symbols=["BTCUSDT"],
            start=datetime(2025, 12, 1),
            end=datetime(2025, 12, 2),
            param_grid={"fast": [5]},
            label="test_error"
        )
        
        # Run search (should not raise)
        results = run_param_search(config)
        
        # Verify error result recorded
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['score'], 0.0)
        self.assertIn('error', results[0]['metrics'])


class TestMetricsComputation(unittest.TestCase):
    """Test metrics computation from log files."""
    
    def test_compute_metrics_nonexistent_file(self):
        """Test handling of nonexistent log file."""
        fake_path = Path("nonexistent.csv")
        metrics = _compute_metrics_from_log(fake_path)
        
        # Should return zero metrics
        self.assertEqual(metrics['total_return_pct'], 0.0)
        self.assertEqual(metrics['total_trades'], 0)


if __name__ == '__main__':
    unittest.main()
