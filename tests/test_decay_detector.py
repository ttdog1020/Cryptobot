"""
Test Decay Detector (Module 32 Step 5)

Tests decay detection logic that compares current profile metrics
against historical optimizer performance.
"""

import asyncio
import unittest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

from optimizer.decay_detector import analyze_profile_decay, DecayStatus


class TestDecayDetector(unittest.TestCase):
    """Test decay detection"""
    
    def setUp(self):
        """Create temp directories for test data"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        
        self.profile_dir = self.base_dir / "profiles"
        self.profile_dir.mkdir()
        
        self.history_dir = self.base_dir / "history"
        self.history_dir.mkdir()
    
    def tearDown(self):
        """Clean up temp directory"""
        self.temp_dir.cleanup()
    
    def run_async(self, coro):
        """Helper to run async functions in sync tests"""
        return asyncio.run(coro)
    
    def test_decay_detector_no_data_returns_no_data(self):
        """Test decay detector returns 'no-data' when no profile exists"""
        # No profile created
        
        status = self.run_async(
            analyze_profile_decay(
                symbol="BTCUSDT",
                strategy="scalping_ema_rsi",
                profile_dir=self.profile_dir,
                history_dir=self.history_dir
            )
        )
        
        self.assertEqual(status.status, "no-data")
        self.assertIn("No profile found", status.reason)
    
    def test_decay_detector_not_enough_trades_returns_no_data(self):
        """Test decay detector returns 'no-data' when profile has insufficient trades"""
        # Create profile with low trade count
        profile = {
            "symbol": "BTCUSDT",
            "strategy": "scalping_ema_rsi",
            "enabled": True,
            "params": {
                "ema_fast": 8,
                "ema_slow": 21,
                "rsi_overbought": 70,
                "rsi_oversold": 30,
                "rsi_period": 14,
                "volume_multiplier": 1.5,
                "timeframe": "15m"
            },
            "meta": {
                "version": 1,
                "created_at": "2025-12-01T10:00:00Z",
                "updated_at": "2025-12-01T10:00:00Z",
                "source": "optimizer",
                "run_id": "run_123",
                "notes": ""
            },
            "metrics": {
                "trades": 10,  # Below default min_trades=50
                "win_rate_pct": 60.0,
                "total_return_pct": 5.0,
                "max_drawdown_pct": 3.0,
                "avg_R_multiple": 1.5,
                "sample_period_days": 7
            }
        }
        
        profile_path = self.profile_dir / "BTCUSDT.json"
        with open(profile_path, 'w') as f:
            json.dump(profile, f)
        
        status = self.run_async(
            analyze_profile_decay(
                symbol="BTCUSDT",
                strategy="scalping_ema_rsi",
                profile_dir=self.profile_dir,
                history_dir=self.history_dir,
                min_trades=50
            )
        )
        
        self.assertEqual(status.status, "no-data")
        self.assertIn("Insufficient trades", status.reason)
        self.assertEqual(status.stats["current_trades"], 10)
    
    def test_decay_detector_healthy_when_within_thresholds(self):
        """Test decay detector returns 'healthy' when metrics are within thresholds"""
        # Create current profile
        profile = {
            "symbol": "BTCUSDT",
            "strategy": "scalping_ema_rsi",
            "enabled": True,
            "params": {
                "ema_fast": 8,
                "ema_slow": 21,
                "rsi_overbought": 70,
                "rsi_oversold": 30,
                "rsi_period": 14,
                "volume_multiplier": 1.5,
                "timeframe": "15m"
            },
            "meta": {
                "version": 1,
                "created_at": "2025-12-05T10:00:00Z",
                "updated_at": "2025-12-05T10:00:00Z",
                "source": "optimizer",
                "run_id": "run_current",
                "notes": ""
            },
            "metrics": {
                "trades": 100,
                "win_rate_pct": 58.0,  # Close to historical best
                "total_return_pct": 10.0,
                "max_drawdown_pct": 5.5,  # Close to historical best
                "avg_R_multiple": 1.8,
                "sample_period_days": 7
            }
        }
        
        profile_path = self.profile_dir / "BTCUSDT.json"
        with open(profile_path, 'w') as f:
            json.dump(profile, f)
        
        # Create historical runs with similar performance
        now = datetime.now(timezone.utc)
        history = [
            {
                "run_id": "run_hist1",
                "created_at": (now - timedelta(days=5)).isoformat().replace('+00:00', 'Z'),
                "strategy": "scalping_ema_rsi",
                "symbols": ["BTCUSDT"],
                "profiles": [
                    {
                        "symbol": "BTCUSDT",
                        "metrics": {
                            "trades": 120,
                            "win_rate_pct": 60.0,  # Best: 60%
                            "total_return_pct": 12.0,
                            "max_drawdown_pct": 5.0,  # Best: 5%
                            "avg_R_multiple": 1.9,
                            "sample_period_days": 7
                        }
                    }
                ]
            }
        ]
        
        history_path = self.history_dir / "history.jsonl"
        with open(history_path, 'w') as f:
            for record in history:
                f.write(json.dumps(record) + '\n')
        
        status = self.run_async(
            analyze_profile_decay(
                symbol="BTCUSDT",
                strategy="scalping_ema_rsi",
                profile_dir=self.profile_dir,
                history_dir=self.history_dir,
                min_trades=50,
                winrate_threshold_pct=15.0,  # Current is 58%, best is 60%, drop is 2% < 15%
                drawdown_threshold_pct=10.0  # Current is 5.5%, best is 5%, increase is 0.5% < 10%
            )
        )
        
        self.assertEqual(status.status, "healthy")
        self.assertIn("within thresholds", status.reason.lower())
        self.assertAlmostEqual(status.stats["current_winrate_pct"], 58.0)
        self.assertAlmostEqual(status.stats["best_winrate_pct"], 60.0)
    
    def test_decay_detector_degraded_when_winrate_drops_too_much(self):
        """Test decay detector returns 'degraded' when win rate drops significantly"""
        # Create current profile with poor win rate
        profile = {
            "symbol": "ETHUSDT",
            "strategy": "scalping_ema_rsi",
            "enabled": True,
            "params": {
                "ema_fast": 5,
                "ema_slow": 13,
                "rsi_overbought": 68,
                "rsi_oversold": 25,
                "rsi_period": 10,
                "volume_multiplier": 2.0,
                "timeframe": "5m"
            },
            "meta": {
                "version": 1,
                "created_at": "2025-12-05T10:00:00Z",
                "updated_at": "2025-12-05T10:00:00Z",
                "source": "optimizer",
                "run_id": "run_current",
                "notes": ""
            },
            "metrics": {
                "trades": 150,
                "win_rate_pct": 40.0,  # Dropped significantly from historical
                "total_return_pct": 2.0,
                "max_drawdown_pct": 8.0,
                "avg_R_multiple": 1.1,
                "sample_period_days": 7
            }
        }
        
        profile_path = self.profile_dir / "ETHUSDT.json"
        with open(profile_path, 'w') as f:
            json.dump(profile, f)
        
        # Create historical runs with better win rate
        now = datetime.now(timezone.utc)
        history = [
            {
                "run_id": "run_hist1",
                "created_at": (now - timedelta(days=3)).isoformat().replace('+00:00', 'Z'),
                "strategy": "scalping_ema_rsi",
                "symbols": ["ETHUSDT"],
                "profiles": [
                    {
                        "symbol": "ETHUSDT",
                        "metrics": {
                            "trades": 200,
                            "win_rate_pct": 62.0,  # Much better than current 40%
                            "total_return_pct": 15.0,
                            "max_drawdown_pct": 6.0,
                            "avg_R_multiple": 2.0,
                            "sample_period_days": 7
                        }
                    }
                ]
            }
        ]
        
        history_path = self.history_dir / "history.jsonl"
        with open(history_path, 'w') as f:
            for record in history:
                f.write(json.dumps(record) + '\n')
        
        status = self.run_async(
            analyze_profile_decay(
                symbol="ETHUSDT",
                strategy="scalping_ema_rsi",
                profile_dir=self.profile_dir,
                history_dir=self.history_dir,
                min_trades=50,
                winrate_threshold_pct=15.0  # Drop of 22% exceeds threshold
            )
        )
        
        self.assertEqual(status.status, "degraded")
        self.assertIn("Win rate dropped", status.reason)
        self.assertAlmostEqual(status.stats["current_winrate_pct"], 40.0)
        self.assertAlmostEqual(status.stats["best_winrate_pct"], 62.0)
        self.assertGreater(status.stats["winrate_drop_pct"], 15.0)
    
    def test_decay_detector_degraded_when_drawdown_worsens(self):
        """Test decay detector returns 'degraded' when drawdown increases significantly"""
        # Create current profile with worse drawdown
        profile = {
            "symbol": "ADAUSDT",
            "strategy": "scalping_ema_rsi",
            "enabled": True,
            "params": {
                "ema_fast": 8,
                "ema_slow": 21,
                "rsi_overbought": 70,
                "rsi_oversold": 30,
                "rsi_period": 14,
                "volume_multiplier": 1.5,
                "timeframe": "15m"
            },
            "meta": {
                "version": 1,
                "created_at": "2025-12-05T10:00:00Z",
                "updated_at": "2025-12-05T10:00:00Z",
                "source": "optimizer",
                "run_id": "run_current",
                "notes": ""
            },
            "metrics": {
                "trades": 80,
                "win_rate_pct": 55.0,
                "total_return_pct": 8.0,
                "max_drawdown_pct": 18.0,  # Much worse than historical
                "avg_R_multiple": 1.5,
                "sample_period_days": 7
            }
        }
        
        profile_path = self.profile_dir / "ADAUSDT.json"
        with open(profile_path, 'w') as f:
            json.dump(profile, f)
        
        # Create historical runs with better drawdown
        now = datetime.now(timezone.utc)
        history = [
            {
                "run_id": "run_hist1",
                "created_at": (now - timedelta(days=7)).isoformat().replace('+00:00', 'Z'),
                "strategy": "scalping_ema_rsi",
                "symbols": ["ADAUSDT"],
                "profiles": [
                    {
                        "symbol": "ADAUSDT",
                        "metrics": {
                            "trades": 90,
                            "win_rate_pct": 56.0,
                            "total_return_pct": 9.0,
                            "max_drawdown_pct": 6.0,  # Much better than current 18%
                            "avg_R_multiple": 1.6,
                            "sample_period_days": 7
                        }
                    }
                ]
            }
        ]
        
        history_path = self.history_dir / "history.jsonl"
        with open(history_path, 'w') as f:
            for record in history:
                f.write(json.dumps(record) + '\n')
        
        status = self.run_async(
            analyze_profile_decay(
                symbol="ADAUSDT",
                strategy="scalping_ema_rsi",
                profile_dir=self.profile_dir,
                history_dir=self.history_dir,
                min_trades=50,
                drawdown_threshold_pct=10.0  # Increase of 12% exceeds threshold
            )
        )
        
        self.assertEqual(status.status, "degraded")
        self.assertIn("drawdown increased", status.reason.lower())
        self.assertAlmostEqual(status.stats["current_drawdown_pct"], 18.0)
        self.assertAlmostEqual(status.stats["best_drawdown_pct"], 6.0)
        self.assertGreater(status.stats["drawdown_increase_pct"], 10.0)


if __name__ == "__main__":
    unittest.main()
