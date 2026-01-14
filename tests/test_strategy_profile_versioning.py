"""
Test Strategy Profile Versioning (Module 32 Step 3)

Tests profile loader's ability to:
1. Handle legacy profiles by populating default meta/metrics
2. Read and preserve new versioned profiles
3. Validate meta and metrics schema correctly
"""

import unittest
import json
import tempfile
from pathlib import Path
from strategies.profile_loader import StrategyProfileLoader


class TestStrategyProfileVersioning(unittest.TestCase):
    """Test profile versioning and backward compatibility"""
    
    def setUp(self):
        """Create temp directory for test profiles"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.profile_dir = Path(self.temp_dir.name)
        self.loader = StrategyProfileLoader(self.profile_dir)
    
    def tearDown(self):
        """Clean up temp directory"""
        self.temp_dir.cleanup()
    
    def test_profile_loader_populates_default_meta_and_metrics_when_missing(self):
        """Test backward compatibility: legacy profiles get default meta/metrics"""
        # Create legacy profile (no meta/metrics)
        legacy_profile = {
            "strategy": "scalping_ema_rsi",
            "ema_fast": 8,
            "ema_slow": 21,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "rsi_period": 14,
            "volume_multiplier": 1.5,
            "timeframe": "15m",
            "enabled": True,
            "source": "manual",
            "as_of": "2025-12-01T10:00:00Z"
        }
        
        # Write legacy profile
        profile_path = self.profile_dir / "BTCUSDT.json"
        with open(profile_path, 'w') as f:
            json.dump(legacy_profile, f)
        
        # Load profile
        result = self.loader.load_profile("BTCUSDT", "scalping_ema_rsi")
        
        # Assert profile loaded successfully
        self.assertIsNotNone(result)
        
        # Assert meta section was created with defaults
        self.assertIn("meta", result)
        self.assertEqual(result["meta"]["version"], 1)
        self.assertEqual(result["meta"]["source"], "manual")
        self.assertIsNone(result["meta"]["run_id"])
        self.assertEqual(result["meta"]["notes"], "")
        
        # Assert metrics section was created with defaults
        self.assertIn("metrics", result)
        self.assertEqual(result["metrics"]["trades"], 0)
        self.assertEqual(result["metrics"]["win_rate_pct"], 0.0)
        self.assertEqual(result["metrics"]["total_return_pct"], 0.0)
        self.assertEqual(result["metrics"]["max_drawdown_pct"], 0.0)
        self.assertEqual(result["metrics"]["avg_R_multiple"], 0.0)
        self.assertEqual(result["metrics"]["sample_period_days"], 0)
        
        # Assert original params preserved
        self.assertEqual(result["ema_fast"], 8)
        self.assertIn("symbol", result)  # Symbol should be populated
    
    def test_profile_loader_reads_meta_and_metrics_when_present(self):
        """Test new versioned profiles preserve meta and metrics"""
        # Create new versioned profile
        versioned_profile = {
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
                "created_at": "2025-12-05T15:30:00Z",
                "updated_at": "2025-12-05T15:30:00Z",
                "source": "optimizer",
                "run_id": "run_20251205_153000",
                "notes": "Best params from grid search"
            },
            "metrics": {
                "trades": 150,
                "win_rate_pct": 58.5,
                "total_return_pct": 12.3,
                "max_drawdown_pct": 8.5,
                "avg_R_multiple": 1.8,
                "sample_period_days": 7
            }
        }
        
        # Write versioned profile
        profile_path = self.profile_dir / "ETHUSDT.json"
        with open(profile_path, 'w') as f:
            json.dump(versioned_profile, f)
        
        # Load profile
        result = self.loader.load_profile("ETHUSDT", "scalping_ema_rsi")
        
        # Assert profile loaded successfully
        self.assertIsNotNone(result)
        
        # Assert meta values preserved
        self.assertEqual(result["meta"]["version"], 1)
        self.assertEqual(result["meta"]["source"], "optimizer")
        self.assertEqual(result["meta"]["run_id"], "run_20251205_153000")
        self.assertEqual(result["meta"]["notes"], "Best params from grid search")
        
        # Assert metrics values preserved
        self.assertEqual(result["metrics"]["trades"], 150)
        self.assertAlmostEqual(result["metrics"]["win_rate_pct"], 58.5)
        self.assertAlmostEqual(result["metrics"]["total_return_pct"], 12.3)
        self.assertAlmostEqual(result["metrics"]["max_drawdown_pct"], 8.5)
        self.assertAlmostEqual(result["metrics"]["avg_R_multiple"], 1.8)
        self.assertEqual(result["metrics"]["sample_period_days"], 7)
        
        # Assert params extracted correctly
        self.assertEqual(result["ema_fast"], 5)
        self.assertEqual(result["ema_slow"], 13)
    
    def test_profile_loader_schema_validation_rejects_bad_meta_types(self):
        """Test validation rejects invalid meta/metrics types"""
        
        # Test 1: meta.version as string instead of int
        bad_version_profile = {
            "symbol": "BTCUSDT",
            "strategy": "scalping_ema_rsi",
            "enabled": True,
            "params": {"ema_fast": 8},
            "meta": {
                "version": "1",  # Should be int, not string
                "created_at": "2025-12-01T10:00:00Z",
                "updated_at": "2025-12-01T10:00:00Z",
                "source": "manual",
                "run_id": None,
                "notes": ""
            },
            "metrics": {
                "trades": 0,
                "win_rate_pct": 0.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "avg_R_multiple": 0.0,
                "sample_period_days": 0
            }
        }
        
        profile_path = self.profile_dir / "BAD_VERSION.json"
        with open(profile_path, 'w') as f:
            json.dump(bad_version_profile, f)
        
        result = self.loader.load_profile("BAD_VERSION", "scalping_ema_rsi")
        self.assertIsNone(result, "Should reject profile with version as string")
        
        # Test 2: metrics.trades as string
        bad_trades_profile = {
            "symbol": "ETHUSDT",
            "strategy": "scalping_ema_rsi",
            "enabled": True,
            "params": {"ema_fast": 8},
            "meta": {
                "version": 1,
                "created_at": "2025-12-01T10:00:00Z",
                "updated_at": "2025-12-01T10:00:00Z",
                "source": "manual",
                "run_id": None,
                "notes": ""
            },
            "metrics": {
                "trades": "zero",  # Should be numeric
                "win_rate_pct": 0.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "avg_R_multiple": 0.0,
                "sample_period_days": 0
            }
        }
        
        profile_path2 = self.profile_dir / "BAD_TRADES.json"
        with open(profile_path2, 'w') as f:
            json.dump(bad_trades_profile, f)
        
        result2 = self.loader.load_profile("BAD_TRADES", "scalping_ema_rsi")
        self.assertIsNone(result2, "Should reject profile with trades as string")
        
        # Test 3: negative trades count
        negative_trades_profile = {
            "symbol": "ADAUSDT",
            "strategy": "scalping_ema_rsi",
            "enabled": True,
            "params": {"ema_fast": 8},
            "meta": {
                "version": 1,
                "created_at": "2025-12-01T10:00:00Z",
                "updated_at": "2025-12-01T10:00:00Z",
                "source": "manual",
                "run_id": None,
                "notes": ""
            },
            "metrics": {
                "trades": -10,  # Negative trades not allowed
                "win_rate_pct": 50.0,
                "total_return_pct": 5.0,
                "max_drawdown_pct": 3.0,
                "avg_R_multiple": 1.2,
                "sample_period_days": 7
            }
        }
        
        profile_path3 = self.profile_dir / "NEGATIVE_TRADES.json"
        with open(profile_path3, 'w') as f:
            json.dump(negative_trades_profile, f)
        
        result3 = self.loader.load_profile("NEGATIVE_TRADES", "scalping_ema_rsi")
        self.assertIsNone(result3, "Should reject profile with negative trades")
    
    def test_save_profile_writes_new_versioned_schema(self):
        """Test save_profile() creates profiles with new schema"""
        # Save a profile
        params = {
            "ema_fast": 8,
            "ema_slow": 21,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "rsi_period": 14,
            "volume_multiplier": 1.5,
            "timeframe": "15m"
        }
        
        metrics = {
            "trades": 100,
            "win_rate_pct": 55.0,
            "total_return_pct": 8.5,
            "max_drawdown_pct": 5.2,
            "avg_R_multiple": 1.6,
            "sample_period_days": 7
        }
        
        saved_path = self.loader.save_profile(
            symbol="BTCUSDT",
            strategy="scalping_ema_rsi",
            params=params,
            metrics=metrics,
            source="optimizer",
            enabled=True,
            run_id="run_test_123"
        )
        
        # Load raw JSON to verify structure
        with open(saved_path, 'r') as f:
            saved_profile = json.load(f)
        
        # Verify new schema structure
        self.assertEqual(saved_profile["symbol"], "BTCUSDT")
        self.assertEqual(saved_profile["strategy"], "scalping_ema_rsi")
        self.assertEqual(saved_profile["enabled"], True)
        
        # Verify params section
        self.assertIn("params", saved_profile)
        self.assertEqual(saved_profile["params"]["ema_fast"], 8)
        
        # Verify meta section
        self.assertIn("meta", saved_profile)
        self.assertEqual(saved_profile["meta"]["version"], 1)
        self.assertEqual(saved_profile["meta"]["source"], "optimizer")
        self.assertEqual(saved_profile["meta"]["run_id"], "run_test_123")
        self.assertIsNotNone(saved_profile["meta"]["created_at"])
        
        # Verify metrics section
        self.assertIn("metrics", saved_profile)
        self.assertEqual(saved_profile["metrics"]["trades"], 100)
        self.assertAlmostEqual(saved_profile["metrics"]["win_rate_pct"], 55.0)


if __name__ == "__main__":
    unittest.main()
