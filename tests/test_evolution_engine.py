"""
Test Auto-Evolution Engine (Module 33)

Tests evolution decision logic and side effects using in-memory data.
"""

import asyncio
import json
import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

from optimizer.evolution_engine import EvolutionEngine, EvolutionDecision
from optimizer.decay_detector import DecayStatus


class DummyProfileLoader:
    """Mock profile loader for testing"""
    
    def __init__(self, tmpdir: Path, profile_data: dict):
        self.tmpdir = tmpdir
        self.profile_dir = tmpdir / "profiles"
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.profile_data = profile_data
        
        # Create actual profile files
        for symbol, data in profile_data.items():
            path = self.profile_dir / f"{symbol}.json"
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
    
    def load_profile(self, symbol, strategy, require_enabled=True):
        path = self.profile_dir / f"{symbol}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    
    def list_symbols(self):
        return list(self.profile_data.keys())


class TestEvolutionEngine(unittest.TestCase):
    """Test evolution engine"""
    
    def setUp(self):
        """Create temp directory for test data"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
    
    def tearDown(self):
        """Clean up temp directory"""
        self.temp_dir.cleanup()
    
    def run_async(self, coro):
        """Helper to run async functions in sync tests"""
        return asyncio.run(coro)
    
    def make_engine(
        self,
        status="degraded",
        old_return=2.0,
        old_dd=1.0,
        new_return=3.0,
        new_dd=1.0,
        dry_run=True,
        new_trades=10
    ):
        """Create test engine with mock data"""
        # Create profile data
        profile_data = {
            "BTCUSDT": {
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
                "metrics": {
                    "total_return_pct": old_return,
                    "max_drawdown_pct": old_dd,
                    "trades": 50,
                    "win_rate_pct": 55.0,
                    "avg_R_multiple": 1.5,
                    "sample_period_days": 7
                },
                "meta": {
                    "version": 1,
                    "source": "optimizer",
                    "created_at": "2025-12-01T10:00:00Z",
                    "updated_at": "2025-12-01T10:00:00Z",
                    "run_id": None,
                    "notes": ""
                },
            }
        }
        
        # Create evolution config
        evo_cfg = {
            "enable_auto_evolution": True,
            "symbols": ["BTCUSDT"],
            "decay_health_thresholds": [status],
            "optimizer_window": {"start_days_ago": 30, "end_days_ago": 0},
            "min_trades": 5,
            "min_return_pct": 0.0,
            "max_dd_pct": 100.0,
            "min_improvement_return_pct": 0.5,
            "max_allowed_dd_increase_pct": 1.0,
            "archive_dir": "archive",
            "log_dir": "logs",
            "dry_run": dry_run,
        }
        
        # Create mock performance history
        history_dir = self.base_dir / "logs" / "performance_history"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "history.jsonl"
        
        # Create history entry with better params
        now = datetime.now(timezone.utc)
        history_entry = {
            "run_id": "test_run_123",
            "created_at": (now - timedelta(days=5)).isoformat().replace('+00:00', 'Z'),
            "strategy": "scalping_ema_rsi",
            "symbols": ["BTCUSDT"],
            "start": "2025-11-01",
            "end": "2025-12-01",
            "interval": "1m",
            "profiles": [
                {
                    "symbol": "BTCUSDT",
                    "params": {
                        "ema_fast": 10,
                        "ema_slow": 20,
                        "rsi_overbought": 68,
                        "rsi_oversold": 25,
                        "rsi_period": 10,
                        "volume_multiplier": 2.0,
                        "timeframe": "15m"
                    },
                    "metrics": {
                        "total_return_pct": new_return,
                        "max_drawdown_pct": new_dd,
                        "trades": new_trades,
                        "win_rate_pct": 60.0,
                        "avg_R_multiple": 1.8,
                        "sample_period_days": 7
                    },
                }
            ]
        }
        
        with history_file.open("w", encoding="utf-8") as f:
            f.write(json.dumps(history_entry) + '\n')
        
        # Create profile loader
        profile_loader = DummyProfileLoader(self.base_dir, profile_data)
        
        # Create engine
        engine = EvolutionEngine(evo_cfg, profile_loader, self.base_dir)
        
        return engine
    
    def test_evolution_accepts_better_profile(self):
        """Test that evolution accepts a better profile"""
        engine = self.make_engine(
            status="degraded",
            old_return=1.0,
            old_dd=1.0,
            new_return=3.0,
            new_dd=1.0,
            dry_run=True
        )
        
        # Mock decay detector to return degraded status
        mock_status = DecayStatus(
            symbol="BTCUSDT",
            strategy="scalping_ema_rsi",
            status="degraded",
            reason="Test degradation",
            stats={}
        )
        
        with patch('optimizer.evolution_engine.analyze_profile_decay', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_status
            decision = self.run_async(engine.evaluate_symbol("BTCUSDT"))
        
        self.assertEqual(decision.status, "APPLY")
        self.assertIsNotNone(decision.new_metrics)
        self.assertGreater(
            decision.new_metrics["total_return_pct"],
            decision.old_metrics["total_return_pct"]
        )
    
    def test_evolution_rejects_if_not_degraded(self):
        """Test that evolution skips healthy profiles"""
        # Create engine with threshold="degraded" but profile is healthy
        engine = self.make_engine(status="degraded")  # threshold is "degraded"
        
        # Mock decay detector to return "healthy" status
        mock_status = DecayStatus(
            symbol="BTCUSDT",
            strategy="scalping_ema_rsi",
            status="healthy",  # profile is healthy, not in threshold
            reason="Profile is healthy",
            stats={}
        )
        
        with patch('optimizer.evolution_engine.analyze_profile_decay', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_status
            decision = self.run_async(engine.evaluate_symbol("BTCUSDT"))
        
        self.assertEqual(decision.status, "SKIP")
        self.assertIn("not in thresholds", decision.reason.lower())
    
    def test_evolution_rejects_if_insufficient_improvement(self):
        """Test that evolution rejects candidates with insufficient improvement"""
        engine = self.make_engine(
            status="degraded",
            old_return=2.0,
            new_return=2.1  # Only 0.1% improvement, needs 0.5%
        )
        
        mock_status = DecayStatus(
            symbol="BTCUSDT",
            strategy="scalping_ema_rsi",
            status="degraded",
            reason="Test degradation",
            stats={}
        )
        
        with patch('optimizer.evolution_engine.analyze_profile_decay', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_status
            decision = self.run_async(engine.evaluate_symbol("BTCUSDT"))
        
        self.assertEqual(decision.status, "REJECT")
        self.assertIn("improvement", decision.reason.lower())
    
    def test_evolution_rejects_if_drawdown_too_high(self):
        """Test that evolution rejects candidates with excessive drawdown increase"""
        engine = self.make_engine(
            status="degraded",
            old_return=2.0,
            old_dd=1.0,
            new_return=5.0,  # Good improvement
            new_dd=3.0  # But 2% drawdown increase > 1% allowed
        )
        
        mock_status = DecayStatus(
            symbol="BTCUSDT",
            strategy="scalping_ema_rsi",
            status="degraded",
            reason="Test degradation",
            stats={}
        )
        
        with patch('optimizer.evolution_engine.analyze_profile_decay', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_status
            decision = self.run_async(engine.evaluate_symbol("BTCUSDT"))
        
        self.assertEqual(decision.status, "REJECT")
        self.assertIn("drawdown", decision.reason.lower())
    
    def test_evolution_rejects_if_insufficient_trades(self):
        """Test that evolution rejects candidates with too few trades"""
        engine = self.make_engine(
            status="degraded",
            old_return=1.0,
            new_return=5.0,
            new_trades=2  # Less than min_trades=5
        )
        
        mock_status = DecayStatus(
            symbol="BTCUSDT",
            strategy="scalping_ema_rsi",
            status="degraded",
            reason="Test degradation",
            stats={}
        )
        
        with patch('optimizer.evolution_engine.analyze_profile_decay', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_status
            decision = self.run_async(engine.evaluate_symbol("BTCUSDT"))
        
        self.assertEqual(decision.status, "REJECT")
        self.assertIn("safety filters", decision.reason.lower())
    
    def test_apply_update_in_dry_run_does_not_modify(self):
        """Test that dry-run mode doesn't modify files"""
        engine = self.make_engine(status="degraded", dry_run=True)
        
        mock_status = DecayStatus(
            symbol="BTCUSDT",
            strategy="scalping_ema_rsi",
            status="degraded",
            reason="Test degradation",
            stats={}
        )
        
        with patch('optimizer.evolution_engine.analyze_profile_decay', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_status
            decision = self.run_async(engine.evaluate_symbol("BTCUSDT"))
        
        self.assertEqual(decision.status, "APPLY")
        
        # Get original profile
        profile_path = engine.profile_loader.profile_dir / "BTCUSDT.json"
        with profile_path.open("r") as f:
            original = json.load(f)
        
        # Apply update
        updated_decision = engine.apply_update("BTCUSDT", decision)
        
        # Profile should be unchanged
        with profile_path.open("r") as f:
            after = json.load(f)
        
        self.assertEqual(original, after)
        self.assertIsNone(updated_decision.archive_path)
    
    def test_apply_update_archives_and_increments_version(self):
        """Test that live mode archives old profile and increments version"""
        engine = self.make_engine(status="degraded", dry_run=False)
        
        mock_status = DecayStatus(
            symbol="BTCUSDT",
            strategy="scalping_ema_rsi",
            status="degraded",
            reason="Test degradation",
            stats={}
        )
        
        with patch('optimizer.evolution_engine.analyze_profile_decay', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_status
            decision = self.run_async(engine.evaluate_symbol("BTCUSDT"))
        
        self.assertEqual(decision.status, "APPLY")
        
        # Apply update
        updated_decision = engine.apply_update("BTCUSDT", decision)
        
        # Check archive was created
        self.assertIsNotNone(updated_decision.archive_path)
        archive = Path(updated_decision.archive_path)
        self.assertTrue(archive.exists())
        
        # Check new profile
        profile_path = engine.profile_loader.profile_dir / "BTCUSDT.json"
        with profile_path.open("r") as f:
            profile = json.load(f)
        
        # Version should be incremented
        self.assertEqual(profile["meta"]["version"], 2)
        self.assertEqual(profile["meta"]["source"], "auto_evolution")
        self.assertIn("parent_run_id", profile["meta"])
        
        # Params should be updated
        self.assertEqual(profile["params"]["ema_fast"], 10)
        self.assertEqual(profile["params"]["ema_slow"], 20)
    
    def test_evolution_log_is_created(self):
        """Test that evolution log is created"""
        engine = self.make_engine(status="degraded", dry_run=True)
        
        mock_status = DecayStatus(
            symbol="BTCUSDT",
            strategy="scalping_ema_rsi",
            status="degraded",
            reason="Test degradation",
            stats={}
        )
        
        with patch('optimizer.evolution_engine.analyze_profile_decay', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_status
            decision = self.run_async(engine.evaluate_symbol("BTCUSDT"))
        
        engine.apply_update("BTCUSDT", decision)
        
        # Check that log file was created
        log_files = list(engine.log_dir.glob("evolution_run_BTCUSDT_*.json"))
        self.assertGreater(len(log_files), 0)
        
        # Read log
        with log_files[0].open("r") as f:
            log = json.load(f)
        
        self.assertEqual(log["symbol"], "BTCUSDT")
        self.assertEqual(log["status"], "APPLY")
        self.assertFalse(log["applied"])  # dry-run
        self.assertIn("config_snapshot", log)


if __name__ == "__main__":
    unittest.main()
