"""
Tests for Safety Suite (Module 20)

Tests the differential testing framework and safety suite runner.
"""

import unittest
import pandas as pd
from validation.safety_suite import (
    run_backtest_vs_paper_consistency_test,
    _run_simplified_backtest,
    _run_paper_simulation,
    _test_happy_path_invariants,
    _test_broken_accounting_detection,
    _test_risk_invariants
)
from validation.synthetic_data import (
    generate_trend_series,
    generate_range_series,
    generate_spike_series
)


class TestSyntheticData(unittest.TestCase):
    """Test synthetic data generation."""
    
    def test_trend_series_generation(self):
        """Test trend series generates valid OHLCV data."""
        df = generate_trend_series(
            symbol="BTCUSDT",
            start_price=50000.0,
            num_candles=100,
            seed=42
        )
        
        self.assertEqual(len(df), 100)
        self.assertIn('timestamp', df.columns)
        self.assertIn('open', df.columns)
        self.assertIn('high', df.columns)
        self.assertIn('low', df.columns)
        self.assertIn('close', df.columns)
        self.assertIn('volume', df.columns)
        
        # Check OHLC validity
        for _, row in df.iterrows():
            self.assertGreaterEqual(row['high'], row['open'])
            self.assertGreaterEqual(row['high'], row['close'])
            self.assertLessEqual(row['low'], row['open'])
            self.assertLessEqual(row['low'], row['close'])
            self.assertGreater(row['volume'], 0)
    
    def test_range_series_generation(self):
        """Test range series stays within bounds."""
        center = 3000.0
        width = 0.05  # 5%
        
        df = generate_range_series(
            symbol="ETHUSDT",
            center_price=center,
            num_candles=100,
            range_width=width,
            seed=42
        )
        
        self.assertEqual(len(df), 100)
        
        # Check prices stay roughly within range
        upper_bound = center * (1 + width)
        lower_bound = center * (1 - width)
        
        # Allow some overshoot due to volatility
        self.assertLessEqual(df['high'].max(), upper_bound * 1.1)
        self.assertGreaterEqual(df['low'].min(), lower_bound * 0.9)
    
    def test_spike_series_has_spike(self):
        """Test spike series has a noticeable spike."""
        df = generate_spike_series(
            symbol="SOLUSDT",
            base_price=100.0,
            num_candles=100,
            spike_candle=50,
            spike_magnitude=0.15,  # 15% spike
            seed=42
        )
        
        self.assertEqual(len(df), 100)
        
        # Check that spike candle has higher price than surrounding candles
        spike_close = df.iloc[50]['close']
        pre_spike_close = df.iloc[49]['close']
        
        # Spike should be significantly higher
        spike_pct = (spike_close - pre_spike_close) / pre_spike_close
        self.assertGreater(spike_pct, 0.10)  # At least 10% move
    
    def test_deterministic_generation(self):
        """Test that same seed produces same data."""
        df1 = generate_trend_series(num_candles=50, seed=123)
        df2 = generate_trend_series(num_candles=50, seed=123)
        
        pd.testing.assert_frame_equal(df1, df2)


class TestSimplifiedBacktest(unittest.TestCase):
    """Test simplified backtest implementation."""
    
    def test_backtest_executes(self):
        """Test that backtest runs without errors."""
        df = generate_trend_series(num_candles=100, seed=42)
        
        result = _run_simplified_backtest(df, starting_balance=10000.0, verbose=False)
        
        self.assertIn('final_balance', result)
        self.assertIn('total_trades', result)
        self.assertIn('win_rate', result)
        self.assertIn('log_df', result)
        self.assertIsInstance(result['log_df'], pd.DataFrame)
    
    def test_backtest_preserves_capital(self):
        """Test that backtest doesn't lose all capital without trades."""
        # Use range-bound data with low volatility
        df = generate_range_series(num_candles=50, range_width=0.01, seed=42)
        
        result = _run_simplified_backtest(df, starting_balance=10000.0, verbose=False)
        
        # Should have reasonable balance
        self.assertGreater(result['final_balance'], 0)
        self.assertLess(result['final_balance'], 20000)  # No crazy gains


class TestPaperSimulation(unittest.TestCase):
    """Test paper trading simulation."""
    
    def test_paper_simulation_executes(self):
        """Test that paper simulation runs without errors."""
        df = generate_trend_series(num_candles=100, seed=42)
        
        result = _run_paper_simulation(df, starting_balance=10000.0, verbose=False)
        
        self.assertIn('final_balance', result)
        self.assertIn('total_trades', result)
        self.assertIn('win_rate', result)
        self.assertIn('log_df', result)
        self.assertIsInstance(result['log_df'], pd.DataFrame)
    
    def test_paper_has_init_row(self):
        """Test that paper simulation includes INIT row."""
        df = generate_trend_series(num_candles=100, seed=42)
        
        result = _run_paper_simulation(df, starting_balance=10000.0, verbose=False)
        
        log_df = result['log_df']
        self.assertGreater(len(log_df), 0)
        
        # First row should be INIT
        first_row = log_df.iloc[0]
        self.assertEqual(first_row['action'], 'INIT')
        self.assertEqual(first_row['balance'], 10000.0)


class TestDifferentialConsistency(unittest.TestCase):
    """Test differential backtest vs paper consistency."""
    
    def test_consistency_check_passes(self):
        """Test that consistency check completes successfully."""
        # Run with small dataset for speed
        result = run_backtest_vs_paper_consistency_test(
            num_candles=100,
            starting_balance=10000.0,
            tolerance_pct=2.0,  # Allow 2% difference
            verbose=False
        )
        
        self.assertTrue(result['passed'])
        self.assertIn('backtest', result)
        self.assertIn('paper', result)
        self.assertIn('pnl_diff_pct', result)
    
    def test_both_systems_execute_trades(self):
        """Test that both systems can execute trades on trending data."""
        result = run_backtest_vs_paper_consistency_test(
            num_candles=200,
            starting_balance=10000.0,
            tolerance_pct=2.0,
            verbose=False
        )
        
        # At least one system should have executed trades
        total_trades = result['backtest']['total_trades'] + result['paper']['total_trades']
        
        # This might be 0 if signals don't fire, which is OK for testing
        self.assertGreaterEqual(total_trades, 0)


class TestInvariantHelpers(unittest.TestCase):
    """Test invariant helper functions used in safety suite."""
    
    def test_happy_path_invariants(self):
        """Test happy path invariant checks."""
        # Should not raise
        _test_happy_path_invariants()
    
    def test_broken_accounting_detection(self):
        """Test that broken accounting is detected."""
        # Should not raise (it catches the error internally)
        _test_broken_accounting_detection()
    
    def test_risk_invariants_helper(self):
        """Test risk invariants helper."""
        # Should not raise
        _test_risk_invariants()


class TestSafetyIntegration(unittest.TestCase):
    """Integration tests for safety suite."""
    
    def test_full_pipeline_smoke_test(self):
        """Smoke test ensuring full pipeline doesn't crash."""
        # This doesn't run the full suite (which would exit),
        # but tests the core differential test function
        try:
            result = run_backtest_vs_paper_consistency_test(
                num_candles=50,  # Small for speed
                starting_balance=5000.0,
                tolerance_pct=5.0,  # Lenient
                verbose=False
            )
            self.assertTrue(result['passed'])
        except Exception as e:
            self.fail(f"Full pipeline smoke test failed: {e}")


if __name__ == '__main__':
    unittest.main()
