"""
Simple Integration Test for Config Backtest

Tests basic functionality without requiring external dependencies.
"""

import unittest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtests.config_backtest import ConfigBacktestRunner


class TestBacktestBasic(unittest.TestCase):
    """Basic tests for backtest runner initialization."""
    
    def test_initialization_with_defaults(self):
        """Test that backtest runner can be initialized."""
        runner = ConfigBacktestRunner(config_path="config/live.yaml")
        
        self.assertIsNotNone(runner)
        self.assertIsNotNone(runner.config)
        self.assertIsNotNone(runner.symbols)
        self.assertIsNotNone(runner.interval)
        
        # Should have default date range (last 24h)
        self.assertIsNotNone(runner.start_date)
        self.assertIsNotNone(runner.end_date)
        self.assertLess(runner.start_date, runner.end_date)
    
    def test_initialization_with_custom_dates(self):
        """Test initialization with custom date range."""
        start = datetime(2025, 12, 1)
        end = datetime(2025, 12, 8)
        
        runner = ConfigBacktestRunner(
            config_path="config/live.yaml",
            start_date=start,
            end_date=end,
            interval="5m"
        )
        
        self.assertEqual(runner.start_date, start)
        self.assertEqual(runner.end_date, end)
        self.assertEqual(runner.interval, "5m")
    
    def test_load_config(self):
        """Test that configuration is loaded correctly."""
        runner = ConfigBacktestRunner(config_path="config/live.yaml")
        
        # Check essential config keys
        self.assertIn("symbols", runner.config)
        self.assertIn("strategy", runner.config)
        
        # Symbols should be a list
        self.assertIsInstance(runner.config["symbols"], list)
        self.assertGreater(len(runner.config["symbols"]), 0)
        
        # Strategy should have type
        self.assertIn("type", runner.config["strategy"])
    
    def test_get_latest_price(self):
        """Test _get_latest_price helper method."""
        runner = ConfigBacktestRunner(config_path="config/live.yaml")
        
        price_data = {
            "BTCUSDT": 50000.0,
            "ETHUSDT": 3000.0
        }
        
        # Should return correct price
        btc_price = runner._get_latest_price("BTCUSDT", price_data)
        self.assertEqual(btc_price, 50000.0)
        
        eth_price = runner._get_latest_price("ETHUSDT", price_data)
        self.assertEqual(eth_price, 3000.0)
        
        # Should raise error for missing symbol
        with self.assertRaises(ValueError):
            runner._get_latest_price("INVALID", price_data)


if __name__ == "__main__":
    unittest.main()
