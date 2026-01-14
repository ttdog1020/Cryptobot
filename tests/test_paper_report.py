"""
MODULE 19: Paper Report Tests

Tests for paper trading performance reporting functionality.
"""

import unittest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

from analytics.paper_report import PaperTradeReport, generate_report


class TestPaperTradeReport(unittest.TestCase):
    """Test PaperTradeReport analysis functionality."""
    
    def setUp(self):
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_sample_log(self, trades: list, filename: str = "test_log.csv") -> Path:
        """
        Create a sample CSV log file for testing.
        
        Args:
            trades: List of trade dicts
            filename: Output filename
            
        Returns:
            Path to created CSV file
        """
        df = pd.DataFrame(trades)
        log_path = self.temp_path / filename
        df.to_csv(log_path, index=False)
        return log_path
    
    def test_load_valid_log(self):
        """Test loading a valid CSV log file."""
        # Create sample log
        now = datetime.now()
        trades = [
            {
                'timestamp': now.isoformat(),
                'session_start': now.isoformat(),
                'order_id': 'order1',
                'symbol': 'BTCUSDT',
                'action': 'OPEN',
                'side': 'LONG',
                'quantity': 0.01,
                'entry_price': 50000.0,
                'fill_price': 50000.0,
                'fill_value': 500.0,
                'commission': 0.25,
                'slippage': 0.25,
                'realized_pnl': 0.0,
                'pnl_pct': 0.0,
                'balance': 999.5,
                'equity': 999.5,
                'open_positions': 1
            },
            {
                'timestamp': (now + timedelta(minutes=5)).isoformat(),
                'session_start': now.isoformat(),
                'order_id': 'order2',
                'symbol': 'BTCUSDT',
                'action': 'CLOSE',
                'side': 'SELL',
                'quantity': 0.01,
                'entry_price': 50000.0,
                'fill_price': 51000.0,
                'fill_value': 510.0,
                'commission': 0.25,
                'slippage': 0.25,
                'realized_pnl': 9.5,
                'pnl_pct': 1.9,
                'balance': 1009.0,
                'equity': 1009.0,
                'open_positions': 0
            }
        ]
        
        log_path = self._create_sample_log(trades)
        
        # Load report
        report = PaperTradeReport(log_path)
        
        self.assertIsNotNone(report.df)
        self.assertEqual(len(report.df), 2)
        self.assertEqual(len(report.trades_df), 1)  # Only CLOSE actions
    
    def test_missing_log_file(self):
        """Test error handling for missing log file."""
        fake_path = self.temp_path / "nonexistent.csv"
        
        with self.assertRaises(FileNotFoundError):
            PaperTradeReport(fake_path)
    
    def test_overall_metrics_single_trade(self):
        """Test overall metrics calculation with one trade."""
        now = datetime.now()
        trades = [
            {
                'timestamp': now.isoformat(),
                'session_start': now.isoformat(),
                'order_id': 'order1',
                'symbol': 'BTCUSDT',
                'action': 'OPEN',
                'side': 'LONG',
                'quantity': 0.01,
                'entry_price': 50000.0,
                'fill_price': 50000.0,
                'fill_value': 500.0,
                'commission': 0.25,
                'slippage': 0.25,
                'realized_pnl': 0.0,
                'pnl_pct': 0.0,
                'balance': 499.5,
                'equity': 999.5,
                'open_positions': 1
            },
            {
                'timestamp': (now + timedelta(minutes=5)).isoformat(),
                'session_start': now.isoformat(),
                'order_id': 'order2',
                'symbol': 'BTCUSDT',
                'action': 'CLOSE',
                'side': 'SELL',
                'quantity': 0.01,
                'entry_price': 50000.0,
                'fill_price': 51000.0,
                'fill_value': 510.0,
                'commission': 0.255,
                'slippage': 0.255,
                'realized_pnl': 9.49,
                'pnl_pct': 1.898,
                'balance': 1008.99,
                'equity': 1008.99,
                'open_positions': 0
            }
        ]
        
        log_path = self._create_sample_log(trades)
        report = PaperTradeReport(log_path)
        
        metrics = report.get_overall_metrics()
        
        # Check basic metrics
        self.assertEqual(metrics['total_trades'], 1)  # 1 closed trade
        self.assertAlmostEqual(metrics['starting_balance'], 999.5, places=1)
        self.assertAlmostEqual(metrics['final_equity'], 1008.99, places=1)
        self.assertGreater(metrics['total_pnl'], 0)  # Made profit
        self.assertEqual(metrics['win_rate'], 100.0)  # 1/1 winning trade
        self.assertAlmostEqual(metrics['largest_win'], 9.49, places=2)
        self.assertEqual(metrics['largest_loss'], 9.49)  # Only one trade, min == max
    
    def test_overall_metrics_mixed_trades(self):
        """Test overall metrics with winning and losing trades."""
        now = datetime.now()
        trades = [
            # Trade 1: Winner
            {
                'timestamp': now.isoformat(),
                'session_start': now.isoformat(),
                'order_id': 'order1',
                'symbol': 'BTCUSDT',
                'action': 'OPEN',
                'side': 'LONG',
                'quantity': 0.01,
                'entry_price': 50000.0,
                'fill_price': 50000.0,
                'fill_value': 500.0,
                'commission': 0.25,
                'slippage': 0.25,
                'realized_pnl': 0.0,
                'pnl_pct': 0.0,
                'balance': 499.5,
                'equity': 999.5,
                'open_positions': 1
            },
            {
                'timestamp': (now + timedelta(minutes=5)).isoformat(),
                'session_start': now.isoformat(),
                'order_id': 'order2',
                'symbol': 'BTCUSDT',
                'action': 'CLOSE',
                'side': 'SELL',
                'quantity': 0.01,
                'entry_price': 50000.0,
                'fill_price': 51000.0,
                'fill_value': 510.0,
                'commission': 0.25,
                'slippage': 0.25,
                'realized_pnl': 9.5,
                'pnl_pct': 1.9,
                'balance': 1008.5,
                'equity': 1008.5,
                'open_positions': 0
            },
            # Trade 2: Loser
            {
                'timestamp': (now + timedelta(minutes=10)).isoformat(),
                'session_start': now.isoformat(),
                'order_id': 'order3',
                'symbol': 'SOLUSDT',
                'action': 'OPEN',
                'side': 'SHORT',
                'quantity': 5.0,
                'entry_price': 100.0,
                'fill_price': 100.0,
                'fill_value': 500.0,
                'commission': 0.25,
                'slippage': 0.25,
                'realized_pnl': 0.0,
                'pnl_pct': 0.0,
                'balance': 1508.25,
                'equity': 1508.25,
                'open_positions': 1
            },
            {
                'timestamp': (now + timedelta(minutes=15)).isoformat(),
                'session_start': now.isoformat(),
                'order_id': 'order4',
                'symbol': 'SOLUSDT',
                'action': 'CLOSE',
                'side': 'BUY',
                'quantity': 5.0,
                'entry_price': 100.0,
                'fill_price': 102.0,
                'fill_value': 510.0,
                'commission': 0.255,
                'slippage': 0.255,
                'realized_pnl': -10.51,
                'pnl_pct': -2.102,
                'balance': 997.49,
                'equity': 997.49,
                'open_positions': 0
            }
        ]
        
        log_path = self._create_sample_log(trades)
        report = PaperTradeReport(log_path)
        
        metrics = report.get_overall_metrics()
        
        self.assertEqual(metrics['total_trades'], 2)  # 2 closed trades
        self.assertEqual(metrics['win_rate'], 50.0)  # 1 win, 1 loss
        self.assertGreater(metrics['largest_win'], 0)
        self.assertLess(metrics['largest_loss'], 0)
    
    def test_per_symbol_breakdown(self):
        """Test per-symbol performance breakdown."""
        now = datetime.now()
        trades = [
            # BTCUSDT winner
            {'timestamp': now.isoformat(), 'session_start': now.isoformat(),
             'order_id': 'o1', 'symbol': 'BTCUSDT', 'action': 'CLOSE', 'side': 'SELL',
             'quantity': 0.01, 'entry_price': 50000.0, 'fill_price': 51000.0,
             'fill_value': 510.0, 'commission': 0.25, 'slippage': 0.25,
             'realized_pnl': 9.5, 'pnl_pct': 1.9, 'balance': 1009.5,
             'equity': 1009.5, 'open_positions': 0},
            
            # SOLUSDT loser
            {'timestamp': (now + timedelta(minutes=5)).isoformat(), 'session_start': now.isoformat(),
             'order_id': 'o2', 'symbol': 'SOLUSDT', 'action': 'CLOSE', 'side': 'BUY',
             'quantity': 5.0, 'entry_price': 100.0, 'fill_price': 102.0,
             'fill_value': 510.0, 'commission': 0.25, 'slippage': 0.25,
             'realized_pnl': -10.5, 'pnl_pct': -2.1, 'balance': 999.0,
             'equity': 999.0, 'open_positions': 0},
            
            # BTCUSDT winner again
            {'timestamp': (now + timedelta(minutes=10)).isoformat(), 'session_start': now.isoformat(),
             'order_id': 'o3', 'symbol': 'BTCUSDT', 'action': 'CLOSE', 'side': 'SELL',
             'quantity': 0.01, 'entry_price': 50000.0, 'fill_price': 50500.0,
             'fill_value': 505.0, 'commission': 0.25, 'slippage': 0.25,
             'realized_pnl': 4.5, 'pnl_pct': 0.9, 'balance': 1003.5,
             'equity': 1003.5, 'open_positions': 0}
        ]
        
        log_path = self._create_sample_log(trades)
        report = PaperTradeReport(log_path)
        
        per_symbol = report.get_per_symbol_metrics()
        
        # Check BTCUSDT
        self.assertIn('BTCUSDT', per_symbol)
        self.assertEqual(per_symbol['BTCUSDT']['trades'], 2)
        self.assertGreater(per_symbol['BTCUSDT']['total_pnl'], 0)
        self.assertEqual(per_symbol['BTCUSDT']['win_rate'], 100.0)
        
        # Check SOLUSDT
        self.assertIn('SOLUSDT', per_symbol)
        self.assertEqual(per_symbol['SOLUSDT']['trades'], 1)
        self.assertLess(per_symbol['SOLUSDT']['total_pnl'], 0)
        self.assertEqual(per_symbol['SOLUSDT']['win_rate'], 0.0)
    
    def test_empty_log(self):
        """Test handling of empty log file."""
        # Create empty log with headers only
        df = pd.DataFrame(columns=[
            'timestamp', 'session_start', 'order_id', 'symbol', 'action', 'side',
            'quantity', 'entry_price', 'fill_price', 'fill_value', 'commission',
            'slippage', 'realized_pnl', 'pnl_pct', 'balance', 'equity', 'open_positions'
        ])
        log_path = self.temp_path / "empty.csv"
        df.to_csv(log_path, index=False)
        
        report = PaperTradeReport(log_path)
        metrics = report.get_overall_metrics()
        
        # Should return zeros/defaults without crashing
        self.assertEqual(metrics['total_trades'], 0)
        self.assertEqual(metrics['win_rate'], 0.0)
        self.assertEqual(metrics['total_pnl'], 0.0)
    
    def test_only_open_positions(self):
        """Test log with only OPEN actions (no closed trades)."""
        now = datetime.now()
        trades = [
            {
                'timestamp': now.isoformat(),
                'session_start': now.isoformat(),
                'order_id': 'order1',
                'symbol': 'BTCUSDT',
                'action': 'OPEN',
                'side': 'LONG',
                'quantity': 0.01,
                'entry_price': 50000.0,
                'fill_price': 50000.0,
                'fill_value': 500.0,
                'commission': 0.25,
                'slippage': 0.25,
                'realized_pnl': 0.0,
                'pnl_pct': 0.0,
                'balance': 499.5,
                'equity': 999.5,
                'open_positions': 1
            }
        ]
        
        log_path = self._create_sample_log(trades)
        report = PaperTradeReport(log_path)
        
        metrics = report.get_overall_metrics()
        
        # No closed trades
        self.assertEqual(metrics['total_trades'], 0)
        self.assertEqual(metrics['win_rate'], 0.0)
    
    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation."""
        now = datetime.now()
        trades = [
            # Start at 1000
            {'timestamp': now.isoformat(), 'session_start': now.isoformat(),
             'order_id': 'o1', 'symbol': 'BTCUSDT', 'action': 'CLOSE', 'side': 'SELL',
             'quantity': 0.01, 'entry_price': 50000.0, 'fill_price': 51000.0,
             'fill_value': 510.0, 'commission': 0.0, 'slippage': 0.0,
             'realized_pnl': 10.0, 'pnl_pct': 1.0, 'balance': 1010.0,
             'equity': 1010.0, 'open_positions': 0},
            
            # Lose money - drawdown starts
            {'timestamp': (now + timedelta(minutes=1)).isoformat(), 'session_start': now.isoformat(),
             'order_id': 'o2', 'symbol': 'BTCUSDT', 'action': 'CLOSE', 'side': 'SELL',
             'quantity': 0.01, 'entry_price': 50000.0, 'fill_price': 49000.0,
             'fill_value': 490.0, 'commission': 0.0, 'slippage': 0.0,
             'realized_pnl': -10.0, 'pnl_pct': -1.0, 'balance': 1000.0,
             'equity': 1000.0, 'open_positions': 0},
            
            # Lose more - max drawdown
            {'timestamp': (now + timedelta(minutes=2)).isoformat(), 'session_start': now.isoformat(),
             'order_id': 'o3', 'symbol': 'BTCUSDT', 'action': 'CLOSE', 'side': 'SELL',
             'quantity': 0.01, 'entry_price': 50000.0, 'fill_price': 48000.0,
             'fill_value': 480.0, 'commission': 0.0, 'slippage': 0.0,
             'realized_pnl': -20.0, 'pnl_pct': -2.0, 'balance': 980.0,
             'equity': 980.0, 'open_positions': 0},
            
            # Recover slightly
            {'timestamp': (now + timedelta(minutes=3)).isoformat(), 'session_start': now.isoformat(),
             'order_id': 'o4', 'symbol': 'BTCUSDT', 'action': 'CLOSE', 'side': 'SELL',
             'quantity': 0.01, 'entry_price': 50000.0, 'fill_price': 50500.0,
             'fill_value': 505.0, 'commission': 0.0, 'slippage': 0.0,
             'realized_pnl': 5.0, 'pnl_pct': 0.5, 'balance': 985.0,
             'equity': 985.0, 'open_positions': 0}
        ]
        
        log_path = self._create_sample_log(trades)
        report = PaperTradeReport(log_path)
        
        metrics = report.get_overall_metrics()
        
        # Max drawdown should be from peak (1010) to trough (980) = 30
        self.assertAlmostEqual(metrics['max_drawdown'], 30.0, places=1)
        # Percentage: 30/1010 * 100 ≈ 2.97%
        self.assertAlmostEqual(metrics['max_drawdown_pct'], 2.97, places=1)
    
    def test_save_json_report(self):
        """Test saving report to JSON file."""
        now = datetime.now()
        trades = [
            {'timestamp': now.isoformat(), 'session_start': now.isoformat(),
             'order_id': 'o1', 'symbol': 'BTCUSDT', 'action': 'CLOSE', 'side': 'SELL',
             'quantity': 0.01, 'entry_price': 50000.0, 'fill_price': 51000.0,
             'fill_value': 510.0, 'commission': 0.25, 'slippage': 0.25,
             'realized_pnl': 9.5, 'pnl_pct': 1.9, 'balance': 1009.5,
             'equity': 1009.5, 'open_positions': 0}
        ]
        
        log_path = self._create_sample_log(trades)
        report = PaperTradeReport(log_path)
        
        output_path = self.temp_path / "report.json"
        report.save_report(output_path, group_by_symbol=True)
        
        # Verify JSON file exists and is valid
        self.assertTrue(output_path.exists())
        
        with open(output_path, 'r') as f:
            data = json.load(f)
        
        self.assertIn('overall', data)
        self.assertIn('per_symbol', data)
        self.assertIn('session', data)
        self.assertEqual(data['overall']['total_trades'], 1)


class TestGenerateReport(unittest.TestCase):
    """Test generate_report CLI function."""
    
    def setUp(self):
        """Create temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_generate_report_basic(self):
        """Test basic report generation (no crash)."""
        # Create minimal valid log
        now = datetime.now()
        trades = [
            {'timestamp': now.isoformat(), 'session_start': now.isoformat(),
             'order_id': 'o1', 'symbol': 'BTCUSDT', 'action': 'CLOSE', 'side': 'SELL',
             'quantity': 0.01, 'entry_price': 50000.0, 'fill_price': 51000.0,
             'fill_value': 510.0, 'commission': 0.25, 'slippage': 0.25,
             'realized_pnl': 9.5, 'pnl_pct': 1.9, 'balance': 1009.5,
             'equity': 1009.5, 'open_positions': 0}
        ]
        
        df = pd.DataFrame(trades)
        log_path = self.temp_path / "test.csv"
        df.to_csv(log_path, index=False)
        
        # Should not crash
        try:
            generate_report(str(log_path), group_by_symbol=False)
        except SystemExit:
            self.fail("generate_report raised SystemExit unexpectedly")


if __name__ == '__main__':
    unittest.main()
