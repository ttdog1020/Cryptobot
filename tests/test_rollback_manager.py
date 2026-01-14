"""
Tests for Rollback Manager and Validator (PR7)
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from optimizer.rollback_manager import (
    ParameterChange,
    ProfileVersion,
    RollbackManager,
    RollbackValidator,
    safe_apply_evolution
)


class TestParameterChange:
    """Test ParameterChange tracking"""
    
    def test_to_dict(self):
        change = ParameterChange(
            name="ema_period",
            old_value=12,
            new_value=14,
            pct_change=16.67
        )
        d = change.to_dict()
        assert d['name'] == "ema_period"
        assert d['old_value'] == 12
        assert d['new_value'] == 14
        assert d['pct_change'] == pytest.approx(16.67, rel=1e-2)


class TestProfileVersion:
    """Test ProfileVersion serialization"""
    
    def test_hash_auto_computation(self):
        pv = ProfileVersion(
            symbol="BTCUSDT",
            strategy="scalping_ema_rsi",
            timestamp="2025-01-15T10:00:00Z",
            params={"ema_period": 12, "rsi_threshold": 30},
            metrics={"return_pct": 5.0, "sharpe": 1.5}
        )
        assert pv.profile_hash != ""
        assert len(pv.profile_hash) == 12
    
    def test_roundtrip_serialization(self):
        pv = ProfileVersion(
            symbol="ETHUSDT",
            strategy="scalping_ema_rsi",
            timestamp="2025-01-15T10:30:00Z",
            params={"ema_period": 15},
            metrics={"return_pct": 3.0, "sharpe": 1.2},
            reason="Evolution run"
        )
        pv.changes_from_prev = [
            ParameterChange(name="ema_period", old_value=12, new_value=15, pct_change=25.0)
        ]
        
        # Serialize and deserialize
        d = pv.to_dict()
        restored = ProfileVersion.from_dict(d)
        
        assert restored.symbol == "ETHUSDT"
        assert restored.params == {"ema_period": 15}
        assert len(restored.changes_from_prev) == 1
        assert restored.changes_from_prev[0].name == "ema_period"


class TestRollbackManager:
    """Test version history and rollback"""
    
    def test_save_and_load_version(self):
        with TemporaryDirectory() as tmpdir:
            manager = RollbackManager(Path(tmpdir))
            
            # Save first version
            v1 = manager.save_version(
                symbol="BTCUSDT",
                strategy="scalping_ema_rsi",
                params={"ema_period": 12, "rsi_threshold": 30},
                metrics={"return_pct": 5.0, "sharpe": 1.5},
                reason="Initial"
            )
            
            # Load and verify
            versions = manager.load_history("BTCUSDT", "scalping_ema_rsi")
            assert len(versions) == 1
            assert versions[0].symbol == "BTCUSDT"
            assert versions[0].params["ema_period"] == 12
    
    def test_version_count(self):
        with TemporaryDirectory() as tmpdir:
            manager = RollbackManager(Path(tmpdir))
            
            # Save 3 versions
            for i in range(3):
                manager.save_version(
                    symbol="BTCUSDT",
                    strategy="scalping_ema_rsi",
                    params={"ema_period": 12 + i},
                    metrics={"return_pct": 5.0 + i},
                    reason=f"Update {i}"
                )
            
            assert manager.get_version_count("BTCUSDT", "scalping_ema_rsi") == 3
    
    def test_most_recent_first(self):
        with TemporaryDirectory() as tmpdir:
            manager = RollbackManager(Path(tmpdir))
            
            # Save 2 versions
            manager.save_version(
                "BTCUSDT", "scalping_ema_rsi",
                {"ema_period": 12}, {"return_pct": 5.0},
                reason="First"
            )
            manager.save_version(
                "BTCUSDT", "scalping_ema_rsi",
                {"ema_period": 14}, {"return_pct": 7.0},
                reason="Second"
            )
            
            # Most recent should be first
            current = manager.get_current_version("BTCUSDT", "scalping_ema_rsi")
            assert current.reason == "Second"
            assert current.params["ema_period"] == 14
    
    def test_parameter_change_tracking(self):
        with TemporaryDirectory() as tmpdir:
            manager = RollbackManager(Path(tmpdir))
            
            # Save first version
            manager.save_version(
                "BTCUSDT", "scalping_ema_rsi",
                {"ema_period": 12, "rsi_threshold": 30},
                {"return_pct": 5.0},
                reason="First"
            )
            
            # Save second with changes
            manager.save_version(
                "BTCUSDT", "scalping_ema_rsi",
                {"ema_period": 14, "rsi_threshold": 25},
                {"return_pct": 7.0},
                reason="Second"
            )
            
            versions = manager.load_history("BTCUSDT", "scalping_ema_rsi")
            changes = versions[0].changes_from_prev
            
            assert len(changes) == 2
            ema_change = [c for c in changes if c.name == "ema_period"][0]
            assert ema_change.old_value == 12
            assert ema_change.new_value == 14
            assert ema_change.pct_change == pytest.approx(16.67, rel=1e-2)
    
    def test_rollback_to_version(self):
        with TemporaryDirectory() as tmpdir:
            manager = RollbackManager(Path(tmpdir))
            
            # Save 3 versions
            for i in range(3):
                manager.save_version(
                    "BTCUSDT", "scalping_ema_rsi",
                    {"ema_period": 12 + i},
                    {"return_pct": 5.0 + i},
                    reason=f"Update {i}"
                )
            
            # Rollback to version 1 (second-most recent)
            target = manager.rollback_to_version("BTCUSDT", "scalping_ema_rsi", 1)
            assert target.reason == "Update 1"
            assert target.params["ema_period"] == 13
    
    def test_rollback_invalid_index(self):
        with TemporaryDirectory() as tmpdir:
            manager = RollbackManager(Path(tmpdir))
            
            manager.save_version(
                "BTCUSDT", "scalping_ema_rsi",
                {"ema_period": 12},
                {"return_pct": 5.0},
                reason="First"
            )
            
            # Out of bounds
            result = manager.rollback_to_version("BTCUSDT", "scalping_ema_rsi", 10)
            assert result is None
    
    def test_list_versions(self):
        with TemporaryDirectory() as tmpdir:
            manager = RollbackManager(Path(tmpdir))
            
            manager.save_version(
                "BTCUSDT", "scalping_ema_rsi",
                {"ema_period": 12},
                {"return_pct": 5.0, "sharpe": 1.5, "max_dd": 10.0},
                reason="First"
            )
            
            versions = manager.list_versions("BTCUSDT", "scalping_ema_rsi")
            assert len(versions) == 1
            assert versions[0]['index'] == 0
            assert versions[0]['return_pct'] == 5.0
            assert versions[0]['reason'] == "First"


class TestRollbackValidator:
    """Test parameter validation"""
    
    def test_parameter_drift_within_tolerance(self):
        validator = RollbackValidator(drift_tolerance_pct=50.0, improvement_threshold_pct=1.0)
        
        valid, msg = validator.validate_update(
            "BTCUSDT",
            {"ema_period": 12, "rsi_threshold": 30},
            {"ema_period": 18, "rsi_threshold": 30},  # 50% increase
            {"return_pct": 5.0},
            {"return_pct": 7.0}  # 40% improvement
        )
        assert valid, msg
    
    def test_parameter_drift_exceeds_tolerance(self):
        validator = RollbackValidator(drift_tolerance_pct=30.0)
        
        # Use 2 params so 1 change = 50% not > 50% (passes chaos check)
        valid, msg = validator.validate_update(
            "BTCUSDT",
            {"ema_period": 12, "rsi_threshold": 30},
            {"ema_period": 20, "rsi_threshold": 30},  # 66% increase
            {"return_pct": 5.0},
            {"return_pct": 10.0}
        )
        assert not valid
        assert "drift" in msg.lower()
    
    def test_improvement_below_threshold(self):
        validator = RollbackValidator(improvement_threshold_pct=5.0)
        
        # Use 2 params so 1 change = 50% not > 50% (passes chaos check)
        valid, msg = validator.validate_update(
            "BTCUSDT",
            {"ema_period": 12, "rsi_threshold": 30},
            {"ema_period": 14, "rsi_threshold": 30},
            {"return_pct": 5.0},
            {"return_pct": 5.2}  # 0.2% improvement
        )
        assert not valid
        assert "improvement" in msg.lower()
    
    def test_negative_parameter_rejection(self):
        validator = RollbackValidator(drift_tolerance_pct=200.0)  # Allow high drift, catch negative
        
        valid, msg = validator.validate_update(
            "BTCUSDT",
            {"stop_loss_pct": 2.0},
            {"stop_loss_pct": -1.0},  # Negative stop loss
            {"return_pct": 5.0},
            {"return_pct": 10.0}
        )
        assert not valid
        assert "negative" in msg.lower()
    
    def test_chaos_threshold(self):
        validator = RollbackValidator(drift_tolerance_pct=200.0, improvement_threshold_pct=5.0)
        
        old_params = {"param1": 1, "param2": 2, "param3": 3}
        new_params = {"param1": 10, "param2": 20, "param3": 30}  # All 3/3 changed = 100% > 50%
        
        valid, msg = validator.validate_update(
            "BTCUSDT",
            old_params,
            new_params,
            {"return_pct": 5.0},
            {"return_pct": 15.0}
        )
        assert not valid, f"Expected validation to fail but got: {msg}"
        assert "chaos" in msg.lower(), f"Expected 'chaos' in message but got: {msg}"


class TestSafeApplyEvolution:
    """Test full safe evolution workflow"""
    
    def test_valid_evolution_applied(self):
        with TemporaryDirectory() as tmpdir:
            manager = RollbackManager(Path(tmpdir))
            # 2 params, 1 changed = 50% not >50%, so passes chaos check
            validator = RollbackValidator(
                drift_tolerance_pct=50.0,
                improvement_threshold_pct=1.0
            )
            
            # First version (2 params to make 1 change not exceed 50% threshold)
            manager.save_version(
                "BTCUSDT", "scalping_ema_rsi",
                {"ema_period": 12, "rsi_threshold": 30},
                {"return_pct": 5.0}
            )
            
            # Apply evolution (1 param change out of 2 = 50%, not > 50%)
            success, msg = safe_apply_evolution(
                "BTCUSDT", "scalping_ema_rsi",
                {"ema_period": 12, "rsi_threshold": 30},
                {"ema_period": 14, "rsi_threshold": 30},
                {"return_pct": 5.0},
                {"return_pct": 7.0},
                manager, validator,
                reason="Good evolution"
            )
            
            assert success, f"Evolution failed: {msg}"
            assert manager.get_version_count("BTCUSDT", "scalping_ema_rsi") == 2
    
    def test_invalid_evolution_rejected(self):
        with TemporaryDirectory() as tmpdir:
            manager = RollbackManager(Path(tmpdir))
            validator = RollbackValidator(improvement_threshold_pct=10.0)
            
            # First version
            manager.save_version(
                "BTCUSDT", "scalping_ema_rsi",
                {"ema_period": 12},
                {"return_pct": 5.0}
            )
            
            # Try to apply bad evolution (insufficient improvement)
            success, msg = safe_apply_evolution(
                "BTCUSDT", "scalping_ema_rsi",
                {"ema_period": 12},
                {"ema_period": 14},
                {"return_pct": 5.0},
                {"return_pct": 5.5},  # Only 0.5% improvement
                manager, validator,
                reason="Bad evolution"
            )
            
            assert not success
            assert manager.get_version_count("BTCUSDT", "scalping_ema_rsi") == 1  # Not saved


class TestEdgeCases:
    """Edge case and error handling"""
    
    def test_empty_history_file(self):
        with TemporaryDirectory() as tmpdir:
            manager = RollbackManager(Path(tmpdir))
            
            # Access non-existent symbol
            versions = manager.load_history("NONEXISTENT", "scalping_ema_rsi")
            assert versions == []
    
    def test_corrupted_history_file(self):
        with TemporaryDirectory() as tmpdir:
            manager = RollbackManager(Path(tmpdir))
            
            # Create corrupted JSON file
            hf = manager._history_file("BTCUSDT", "scalping_ema_rsi")
            with open(hf, 'w') as f:
                f.write("{ invalid json }")
            
            # Should handle gracefully
            versions = manager.load_history("BTCUSDT", "scalping_ema_rsi")
            assert versions == []
    
    def test_parameter_division_by_zero(self):
        """Test handling of zero old value in drift calculation"""
        validator = RollbackValidator()
        
        # Old value is 0, new value is non-zero
        valid, msg = validator.validate_update(
            "BTCUSDT",
            {"new_param": 0},
            {"new_param": 5},
            {"return_pct": 5.0},
            {"return_pct": 10.0}
        )
        # Should handle gracefully (treat as infinite drift, reject)
        assert not valid or "drift" in msg.lower()
