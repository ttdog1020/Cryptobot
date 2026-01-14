"""
Tests for StrategyProfileLoader (Module 31)
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

from strategies.profile_loader import StrategyProfileLoader


class TestProfileLoader(unittest.TestCase):
    """Test strategy profile loading functionality"""
    
    def setUp(self):
        """Create temporary directory for test profiles"""
        self.temp_dir = TemporaryDirectory()
        self.profile_dir = Path(self.temp_dir.name)
        self.loader = StrategyProfileLoader(profile_dir=str(self.profile_dir))
    
    def tearDown(self):
        """Clean up temporary directory"""
        self.temp_dir.cleanup()
    
    def _create_profile(self, symbol: str, profile_data: dict):
        """Helper to create a test profile file"""
        profile_path = self.profile_dir / f"{symbol}.json"
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)
        return profile_path
    
    def test_load_valid_profile(self):
        """Should load valid profile successfully"""
        profile_data = {
            "strategy": "scalping_ema_rsi",
            "ema_fast": 8,
            "ema_slow": 21,
            "rsi_overbought": 68,
            "rsi_oversold": 30,
            "enabled": True,
            "source": "optimizer_v1",
            "as_of": "2025-12-08T12:00:00Z"
        }
        self._create_profile("BTCUSDT", profile_data)
        
        result = self.loader.load_profile("BTCUSDT", "scalping_ema_rsi")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["ema_fast"], 8)
        self.assertEqual(result["ema_slow"], 21)
        self.assertEqual(result["rsi_overbought"], 68)
        self.assertEqual(result["rsi_oversold"], 30)
        # Metadata should be filtered out
        self.assertNotIn("strategy", result)
        self.assertNotIn("enabled", result)
        self.assertNotIn("source", result)
    
    def test_load_missing_profile(self):
        """Should return None when profile doesn't exist"""
        result = self.loader.load_profile("ETHUSDT", "scalping_ema_rsi")
        self.assertIsNone(result)
    
    def test_load_disabled_profile(self):
        """Should return None when profile is disabled"""
        profile_data = {
            "strategy": "scalping_ema_rsi",
            "ema_fast": 10,
            "enabled": False
        }
        self._create_profile("BTCUSDT", profile_data)
        
        result = self.loader.load_profile("BTCUSDT", "scalping_ema_rsi")
        self.assertIsNone(result)
    
    def test_load_disabled_profile_when_not_required(self):
        """Should return profile when disabled but require_enabled=False"""
        profile_data = {
            "strategy": "scalping_ema_rsi",
            "ema_fast": 10,
            "enabled": False
        }
        self._create_profile("BTCUSDT", profile_data)
        
        result = self.loader.load_profile(
            "BTCUSDT",
            "scalping_ema_rsi",
            require_enabled=False
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result["ema_fast"], 10)
    
    def test_load_invalid_json(self):
        """Should return None and log warning for invalid JSON"""
        profile_path = self.profile_dir / "BTCUSDT.json"
        with open(profile_path, 'w') as f:
            f.write("{invalid json")
        
        result = self.loader.load_profile("BTCUSDT", "scalping_ema_rsi")
        self.assertIsNone(result)
    
    def test_load_missing_required_fields(self):
        """Should return None when required fields are missing"""
        # Missing 'enabled' field
        profile_data = {
            "strategy": "scalping_ema_rsi",
            "ema_fast": 8
        }
        self._create_profile("BTCUSDT", profile_data)
        
        result = self.loader.load_profile("BTCUSDT", "scalping_ema_rsi")
        self.assertIsNone(result)
    
    def test_load_wrong_strategy(self):
        """Should return None when strategy doesn't match"""
        profile_data = {
            "strategy": "different_strategy",
            "enabled": True
        }
        self._create_profile("BTCUSDT", profile_data)
        
        result = self.loader.load_profile("BTCUSDT", "scalping_ema_rsi")
        self.assertIsNone(result)
    
    def test_load_profile_with_metrics(self):
        """Should load profile with metrics correctly (Module 32: metrics now included)"""
        profile_data = {
            "strategy": "scalping_ema_rsi",
            "ema_fast": 8,
            "enabled": True,
            "metrics": {
                "total_return_pct": 10.5,
                "max_dd_pct": 2.3,
                "trades": 15
            }
        }
        self._create_profile("BTCUSDT", profile_data)
        
        result = self.loader.load_profile("BTCUSDT", "scalping_ema_rsi")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["ema_fast"], 8)
        # Module 32: Metrics should now be included in the result
        self.assertIn("metrics", result)
        self.assertEqual(result["metrics"]["total_return_pct"], 10.5)
        self.assertEqual(result["metrics"]["trades"], 15)
    
    def test_load_all_profiles(self):
        """Should load all enabled profiles for a strategy"""
        # Create multiple profiles
        profiles = {
            "BTCUSDT": {
                "strategy": "scalping_ema_rsi",
                "ema_fast": 8,
                "enabled": True
            },
            "ETHUSDT": {
                "strategy": "scalping_ema_rsi",
                "ema_fast": 10,
                "enabled": True
            },
            "BNBUSDT": {
                "strategy": "scalping_ema_rsi",
                "ema_fast": 12,
                "enabled": False  # Should be skipped
            },
            "SOLUSDT": {
                "strategy": "different_strategy",  # Should be skipped
                "ema_fast": 5,
                "enabled": True
            }
        }
        
        for symbol, data in profiles.items():
            self._create_profile(symbol, data)
        
        result = self.loader.load_all_profiles("scalping_ema_rsi")
        
        # Should only include BTCUSDT and ETHUSDT
        self.assertEqual(len(result), 2)
        self.assertIn("BTCUSDT", result)
        self.assertIn("ETHUSDT", result)
        self.assertNotIn("BNBUSDT", result)  # Disabled
        self.assertNotIn("SOLUSDT", result)  # Wrong strategy
        
        self.assertEqual(result["BTCUSDT"]["ema_fast"], 8)
        self.assertEqual(result["ETHUSDT"]["ema_fast"], 10)
    
    def test_load_all_profiles_skip_example_files(self):
        """Should skip files starting with EXAMPLE_"""
        # Create example file
        example_data = {
            "strategy": "scalping_ema_rsi",
            "ema_fast": 99,
            "enabled": True
        }
        self._create_profile("EXAMPLE_BTCUSDT", example_data)
        
        # Create real profile
        real_data = {
            "strategy": "scalping_ema_rsi",
            "ema_fast": 8,
            "enabled": True
        }
        self._create_profile("BTCUSDT", real_data)
        
        result = self.loader.load_all_profiles("scalping_ema_rsi")
        
        # Should only include real profile
        self.assertEqual(len(result), 1)
        self.assertIn("BTCUSDT", result)
        self.assertNotIn("EXAMPLE_BTCUSDT", result)


class TestProfileSaver(unittest.TestCase):
    """Test strategy profile saving functionality"""
    
    def setUp(self):
        """Create temporary directory for test profiles"""
        self.temp_dir = TemporaryDirectory()
        self.profile_dir = Path(self.temp_dir.name)
        self.loader = StrategyProfileLoader(profile_dir=str(self.profile_dir))
    
    def tearDown(self):
        """Clean up temporary directory"""
        self.temp_dir.cleanup()
    
    def test_save_profile_basic(self):
        """Should save profile with basic parameters"""
        params = {
            "ema_fast": 8,
            "ema_slow": 21,
            "rsi_overbought": 68
        }
        
        path = self.loader.save_profile(
            "BTCUSDT",
            "scalping_ema_rsi",
            params
        )
        
        self.assertTrue(path.exists())
        
        # Verify saved content (Module 32: new versioned schema)
        with open(path, 'r') as f:
            saved = json.load(f)
        
        self.assertEqual(saved["symbol"], "BTCUSDT")
        self.assertEqual(saved["strategy"], "scalping_ema_rsi")
        self.assertEqual(saved["params"]["ema_fast"], 8)
        self.assertEqual(saved["params"]["ema_slow"], 21)
        self.assertEqual(saved["params"]["rsi_overbought"], 68)
        self.assertTrue(saved["enabled"])
        self.assertEqual(saved["meta"]["source"], "optimizer")
        self.assertEqual(saved["meta"]["version"], 1)
        self.assertIn("created_at", saved["meta"])
        self.assertIn("metrics", saved)
    
    def test_save_profile_with_metrics(self):
        """Should save profile with metrics"""
        params = {"ema_fast": 8}
        metrics = {
            "total_return_pct": 15.2,
            "max_dd_pct": 3.1,
            "trades": 20
        }
        
        path = self.loader.save_profile(
            "ETHUSDT",
            "scalping_ema_rsi",
            params,
            metrics=metrics
        )
        
        # Verify metrics saved
        with open(path, 'r') as f:
            saved = json.load(f)
        
        self.assertIn("metrics", saved)
        self.assertEqual(saved["metrics"]["total_return_pct"], 15.2)
        self.assertEqual(saved["metrics"]["max_dd_pct"], 3.1)
        self.assertEqual(saved["metrics"]["trades"], 20)
    
    def test_save_profile_custom_source(self):
        """Should save profile with custom source"""
        params = {"ema_fast": 8}
        
        path = self.loader.save_profile(
            "BNBUSDT",
            "scalping_ema_rsi",
            params,
            source="manual_override"
        )
        
        with open(path, 'r') as f:
            saved = json.load(f)
        
        self.assertEqual(saved["meta"]["source"], "manual_override")
    
    def test_save_profile_disabled(self):
        """Should save disabled profile"""
        params = {"ema_fast": 8}
        
        path = self.loader.save_profile(
            "SOLUSDT",
            "scalping_ema_rsi",
            params,
            enabled=False
        )
        
        with open(path, 'r') as f:
            saved = json.load(f)
        
        self.assertFalse(saved["enabled"])
    
    def test_save_and_load_roundtrip(self):
        """Should successfully save and load profile"""
        params = {
            "ema_fast": 12,
            "ema_slow": 26,
            "rsi_period": 7
        }
        metrics = {
            "total_return_pct": 8.5,
            "trades": 25
        }
        
        # Save
        self.loader.save_profile(
            "ADAUSDT",
            "scalping_ema_rsi",
            params,
            metrics=metrics
        )
        
        # Load
        loaded = self.loader.load_profile("ADAUSDT", "scalping_ema_rsi")
        
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["ema_fast"], 12)
        self.assertEqual(loaded["ema_slow"], 26)
        self.assertEqual(loaded["rsi_period"], 7)


class TestProfileValidation(unittest.TestCase):
    """Test profile validation logic"""
    
    def setUp(self):
        """Create temporary directory"""
        self.temp_dir = TemporaryDirectory()
        self.profile_dir = Path(self.temp_dir.name)
        self.loader = StrategyProfileLoader(profile_dir=str(self.profile_dir))
    
    def tearDown(self):
        """Clean up"""
        self.temp_dir.cleanup()
    
    def test_invalid_enabled_type(self):
        """Should reject profile with non-boolean enabled field"""
        profile_data = {
            "strategy": "scalping_ema_rsi",
            "enabled": "yes"  # Should be boolean
        }
        
        profile_path = self.profile_dir / "BTCUSDT.json"
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)
        
        result = self.loader.load_profile("BTCUSDT", "scalping_ema_rsi")
        self.assertIsNone(result)
    
    def test_invalid_metrics_type(self):
        """Should reject profile with non-dict metrics field"""
        profile_data = {
            "strategy": "scalping_ema_rsi",
            "enabled": True,
            "metrics": "invalid"  # Should be dict
        }
        
        profile_path = self.profile_dir / "BTCUSDT.json"
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)
        
        result = self.loader.load_profile("BTCUSDT", "scalping_ema_rsi")
        self.assertIsNone(result)
    
    def test_invalid_timestamp_nonfatal(self):
        """Should load profile despite invalid timestamp (non-fatal error)"""
        profile_data = {
            "strategy": "scalping_ema_rsi",
            "enabled": True,
            "ema_fast": 8,
            "as_of": "not-a-timestamp"
        }
        
        profile_path = self.profile_dir / "BTCUSDT.json"
        with open(profile_path, 'w') as f:
            json.dump(profile_data, f)
        
        # Should still load (timestamp validation is non-fatal)
        result = self.loader.load_profile("BTCUSDT", "scalping_ema_rsi")
        self.assertIsNotNone(result)
        self.assertEqual(result["ema_fast"], 8)


if __name__ == '__main__':
    unittest.main()
