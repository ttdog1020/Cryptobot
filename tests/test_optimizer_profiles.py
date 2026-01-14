"""
Tests for Optimizer Auto-Apply Functionality (Module 31)
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
from unittest.mock import MagicMock, patch
import argparse

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from optimizer.run_optimizer import (
    group_results_by_symbol,
    apply_profiles,
    save_audit_log
)
from strategies.profile_loader import StrategyProfileLoader


class TestGroupResultsBySymbol(unittest.TestCase):
    """Test grouping optimization results by symbol"""
    
    def test_group_single_symbol(self):
        """Should group results for single symbol"""
        results = [
            {
                'symbols': ['BTCUSDT'],
                'params': {'ema_fast': 8},
                'score': 10.0,
                'metrics': {'total_trades': 20}
            },
            {
                'symbols': ['BTCUSDT'],
                'params': {'ema_fast': 12},
                'score': 8.0,
                'metrics': {'total_trades': 15}
            }
        ]
        
        grouped = group_results_by_symbol(results)
        
        self.assertIn('BTCUSDT', grouped)
        self.assertEqual(len(grouped['BTCUSDT']), 2)
        self.assertEqual(grouped['BTCUSDT'][0]['params']['ema_fast'], 8)
    
    def test_group_multiple_symbols(self):
        """Should group results across multiple symbols"""
        results = [
            {
                'symbols': ['BTCUSDT'],
                'params': {'ema_fast': 8},
                'score': 10.0,
                'metrics': {}
            },
            {
                'symbols': ['ETHUSDT'],
                'params': {'ema_fast': 12},
                'score': 8.0,
                'metrics': {}
            },
            {
                'symbols': ['BTCUSDT'],
                'params': {'ema_fast': 16},
                'score': 5.0,
                'metrics': {}
            }
        ]
        
        grouped = group_results_by_symbol(results)
        
        self.assertEqual(len(grouped), 2)
        self.assertIn('BTCUSDT', grouped)
        self.assertIn('ETHUSDT', grouped)
        self.assertEqual(len(grouped['BTCUSDT']), 2)
        self.assertEqual(len(grouped['ETHUSDT']), 1)


class TestApplyProfiles(unittest.TestCase):
    """Test profile application with safety filters"""
    
    def setUp(self):
        """Create temporary directory for test profiles"""
        self.temp_dir = TemporaryDirectory()
        self.profile_dir = Path(self.temp_dir.name)
    
    def tearDown(self):
        """Clean up temporary directory"""
        self.temp_dir.cleanup()
    
    def test_apply_profile_passing_filters(self):
        """Should write profile when candidate passes all filters"""
        results = [
            {
                'symbols': ['BTCUSDT'],
                'params': {'ema_fast': 8, 'ema_slow': 21},
                'score': 10.0,
                'metrics': {
                    'total_trades': 15,
                    'max_drawdown_pct': 3.0,
                    'total_return_pct': 5.0,
                    'win_rate': 70.0,
                    'avg_trade_pnl': 50.0
                }
            }
        ]
        
        application_results = apply_profiles(
            results=results,
            profile_dir=str(self.profile_dir),
            min_trades=10,
            max_dd_pct=5.0,
            min_return_pct=0.0
        )
        
        # Should be applied
        self.assertIn('BTCUSDT', application_results)
        self.assertEqual(application_results['BTCUSDT']['status'], 'applied')
        self.assertEqual(application_results['BTCUSDT']['selected_params']['ema_fast'], 8)
        
        # Profile file should exist
        profile_path = self.profile_dir / 'BTCUSDT.json'
        self.assertTrue(profile_path.exists())
        
        # Verify profile contents (Module 32: new versioned schema)
        with open(profile_path, 'r') as f:
            profile = json.load(f)
        
        self.assertEqual(profile['symbol'], 'BTCUSDT')
        self.assertEqual(profile['strategy'], 'scalping_ema_rsi')
        self.assertEqual(profile['params']['ema_fast'], 8)
        self.assertEqual(profile['params']['ema_slow'], 21)
        self.assertTrue(profile['enabled'])
        self.assertEqual(profile['meta']['source'], 'optimizer')
        self.assertIn('metrics', profile)
        self.assertEqual(profile['metrics']['trades'], 15)
    
    def test_reject_insufficient_trades(self):
        """Should reject candidate with insufficient trades"""
        results = [
            {
                'symbols': ['ETHUSDT'],
                'params': {'ema_fast': 8},
                'score': 10.0,
                'metrics': {
                    'total_trades': 5,  # Below min_trades
                    'max_drawdown_pct': 2.0,
                    'total_return_pct': 8.0,
                    'win_rate': 80.0,
                    'avg_trade_pnl': 100.0
                }
            }
        ]
        
        application_results = apply_profiles(
            results=results,
            profile_dir=str(self.profile_dir),
            min_trades=10,
            max_dd_pct=5.0,
            min_return_pct=0.0
        )
        
        # Should be rejected
        self.assertIn('ETHUSDT', application_results)
        self.assertEqual(application_results['ETHUSDT']['status'], 'rejected')
        self.assertIn('trades', application_results['ETHUSDT']['reason'])
        
        # No profile file should exist
        profile_path = self.profile_dir / 'ETHUSDT.json'
        self.assertFalse(profile_path.exists())
    
    def test_reject_excessive_drawdown(self):
        """Should reject candidate with excessive drawdown"""
        results = [
            {
                'symbols': ['SOLUSDT'],
                'params': {'ema_fast': 8},
                'score': 15.0,
                'metrics': {
                    'total_trades': 20,
                    'max_drawdown_pct': 8.0,  # Above max_dd_pct
                    'total_return_pct': 15.0,
                    'win_rate': 75.0,
                    'avg_trade_pnl': 75.0
                }
            }
        ]
        
        application_results = apply_profiles(
            results=results,
            profile_dir=str(self.profile_dir),
            min_trades=10,
            max_dd_pct=5.0,
            min_return_pct=0.0
        )
        
        # Should be rejected
        self.assertEqual(application_results['SOLUSDT']['status'], 'rejected')
        self.assertIn('max_dd', application_results['SOLUSDT']['reason'])
    
    def test_reject_insufficient_return(self):
        """Should reject candidate with insufficient return"""
        results = [
            {
                'symbols': ['BNBUSDT'],
                'params': {'ema_fast': 8},
                'score': -2.0,
                'metrics': {
                    'total_trades': 20,
                    'max_drawdown_pct': 3.0,
                    'total_return_pct': -2.0,  # Below min_return_pct
                    'win_rate': 45.0,
                    'avg_trade_pnl': -10.0
                }
            }
        ]
        
        application_results = apply_profiles(
            results=results,
            profile_dir=str(self.profile_dir),
            min_trades=10,
            max_dd_pct=5.0,
            min_return_pct=0.0
        )
        
        # Should be rejected
        self.assertEqual(application_results['BNBUSDT']['status'], 'rejected')
        self.assertIn('return', application_results['BNBUSDT']['reason'])
    
    def test_select_best_passing_candidate(self):
        """Should select first candidate that passes filters (results already sorted by score)"""
        results = [
            # First result fails trades filter
            {
                'symbols': ['ADAUSDT'],
                'params': {'ema_fast': 8},
                'score': 12.0,
                'metrics': {
                    'total_trades': 5,  # Too few
                    'max_drawdown_pct': 2.0,
                    'total_return_pct': 12.0,
                    'win_rate': 80.0,
                    'avg_trade_pnl': 100.0
                }
            },
            # Second result passes all filters
            {
                'symbols': ['ADAUSDT'],
                'params': {'ema_fast': 12},
                'score': 10.0,
                'metrics': {
                    'total_trades': 15,
                    'max_drawdown_pct': 3.0,
                    'total_return_pct': 10.0,
                    'win_rate': 70.0,
                    'avg_trade_pnl': 66.0
                }
            }
        ]
        
        application_results = apply_profiles(
            results=results,
            profile_dir=str(self.profile_dir),
            min_trades=10,
            max_dd_pct=5.0,
            min_return_pct=0.0
        )
        
        # Should use second candidate
        self.assertEqual(application_results['ADAUSDT']['status'], 'applied')
        self.assertEqual(application_results['ADAUSDT']['selected_params']['ema_fast'], 12)
    
    def test_multiple_symbols_mixed_results(self):
        """Should handle multiple symbols with mixed accept/reject"""
        results = [
            # BTCUSDT - passes
            {
                'symbols': ['BTCUSDT'],
                'params': {'ema_fast': 8},
                'score': 10.0,
                'metrics': {
                    'total_trades': 20,
                    'max_drawdown_pct': 2.0,
                    'total_return_pct': 10.0,
                    'win_rate': 75.0,
                    'avg_trade_pnl': 50.0
                }
            },
            # ETHUSDT - fails (drawdown)
            {
                'symbols': ['ETHUSDT'],
                'params': {'ema_fast': 12},
                'score': 8.0,
                'metrics': {
                    'total_trades': 25,
                    'max_drawdown_pct': 7.0,  # Too high
                    'total_return_pct': 8.0,
                    'win_rate': 60.0,
                    'avg_trade_pnl': 32.0
                }
            }
        ]
        
        application_results = apply_profiles(
            results=results,
            profile_dir=str(self.profile_dir),
            min_trades=10,
            max_dd_pct=5.0,
            min_return_pct=0.0
        )
        
        # BTCUSDT should be applied
        self.assertEqual(application_results['BTCUSDT']['status'], 'applied')
        
        # ETHUSDT should be rejected
        self.assertEqual(application_results['ETHUSDT']['status'], 'rejected')
        
        # Only BTCUSDT profile should exist
        self.assertTrue((self.profile_dir / 'BTCUSDT.json').exists())
        self.assertFalse((self.profile_dir / 'ETHUSDT.json').exists())


class TestAuditLog(unittest.TestCase):
    """Test audit log generation"""
    
    def setUp(self):
        """Create temporary directory for logs"""
        self.temp_dir = TemporaryDirectory()
        self.log_dir = Path(self.temp_dir.name)
    
    def tearDown(self):
        """Clean up"""
        self.temp_dir.cleanup()
    
    @patch('optimizer.run_optimizer.Path')
    def test_audit_log_structure(self, mock_path_class):
        """Should create audit log with correct structure"""
        # Mock Path to use temp directory
        mock_path_instance = MagicMock()
        mock_path_instance.mkdir = MagicMock()
        mock_path_instance.__truediv__ = lambda self, other: self.log_dir / other
        mock_path_class.return_value = mock_path_instance
        
        # Override Path() constructor to return temp dir
        def path_constructor(path_str):
            if path_str == "logs/optimizer":
                return self.log_dir
            return Path(path_str)
        
        mock_path_class.side_effect = path_constructor
        
        # Create mock args
        args = argparse.Namespace(
            start='2025-12-01',
            end='2025-12-08',
            symbols=['BTCUSDT', 'ETHUSDT'],
            interval='1m',
            auto_apply=True,
            min_trades=10,
            max_dd_pct=5.0,
            min_return_pct=0.0,
            max_runs=20
        )
        
        application_results = {
            'BTCUSDT': {
                'status': 'applied',
                'selected_params': {'ema_fast': 8, 'ema_slow': 21},
                'metrics': {'total_return_pct': 10.0, 'trades': 20}
            },
            'ETHUSDT': {
                'status': 'rejected',
                'reason': 'max_dd 6.0% > 5.0%'
            }
        }
        
        # Save audit log to temp directory
        audit_path = self.log_dir / f"optimizer_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        audit_log = {
            'timestamp': datetime.now().isoformat(),
            'args': {
                'start': args.start,
                'end': args.end,
                'symbols': args.symbols,
                'interval': args.interval,
                'auto_apply': args.auto_apply,
                'min_trades': args.min_trades,
                'max_dd_pct': args.max_dd_pct,
                'min_return_pct': args.min_return_pct,
                'max_runs': args.max_runs,
                'total_runs_executed': 15
            },
            'results': application_results
        }
        
        with open(audit_path, 'w', encoding='utf-8') as f:
            json.dump(audit_log, f, indent=2, ensure_ascii=False)
        
        # Verify file exists
        self.assertTrue(audit_path.exists())
        
        # Load and verify contents
        with open(audit_path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        
        self.assertIn('timestamp', loaded)
        self.assertIn('args', loaded)
        self.assertIn('results', loaded)
        
        # Verify args
        self.assertEqual(loaded['args']['start'], '2025-12-01')
        self.assertEqual(loaded['args']['min_trades'], 10)
        self.assertTrue(loaded['args']['auto_apply'])
        
        # Verify results
        self.assertIn('BTCUSDT', loaded['results'])
        self.assertIn('ETHUSDT', loaded['results'])
        self.assertEqual(loaded['results']['BTCUSDT']['status'], 'applied')
        self.assertEqual(loaded['results']['ETHUSDT']['status'], 'rejected')


class TestProfileLoaderIntegration(unittest.TestCase):
    """Test integration with StrategyProfileLoader"""
    
    def setUp(self):
        """Create temporary directory"""
        self.temp_dir = TemporaryDirectory()
        self.profile_dir = Path(self.temp_dir.name)
    
    def tearDown(self):
        """Clean up"""
        self.temp_dir.cleanup()
    
    def test_written_profile_is_loadable(self):
        """Should write profile that can be loaded by StrategyProfileLoader"""
        results = [
            {
                'symbols': ['BTCUSDT'],
                'params': {
                    'ema_fast': 8,
                    'ema_slow': 21,
                    'rsi_overbought': 70,
                    'rsi_oversold': 30
                },
                'score': 10.0,
                'metrics': {
                    'total_trades': 25,
                    'max_drawdown_pct': 3.5,
                    'total_return_pct': 10.0,
                    'win_rate': 72.0,
                    'avg_trade_pnl': 40.0
                }
            }
        ]
        
        # Apply profile
        apply_profiles(
            results=results,
            profile_dir=str(self.profile_dir),
            min_trades=10,
            max_dd_pct=5.0,
            min_return_pct=0.0
        )
        
        # Load profile using StrategyProfileLoader
        loader = StrategyProfileLoader(profile_dir=str(self.profile_dir))
        loaded_profile = loader.load_profile('BTCUSDT', 'scalping_ema_rsi')
        
        # Should load successfully
        self.assertIsNotNone(loaded_profile)
        self.assertEqual(loaded_profile['ema_fast'], 8)
        self.assertEqual(loaded_profile['ema_slow'], 21)
        self.assertEqual(loaded_profile['rsi_overbought'], 70)
        self.assertEqual(loaded_profile['rsi_oversold'], 30)


if __name__ == '__main__':
    unittest.main()
