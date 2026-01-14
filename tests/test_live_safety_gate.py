"""
Tests for Live Trading Safety Gate

Verifies the two-key safety gate system that prevents accidental live trading.
"""

import pytest
import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from execution.live_trading_gate import (
    check_live_trading_gate,
    validate_no_live_keys_in_safe_mode,
    LiveTradingGateError,
    enforce_paper_mode_default,
    log_trading_mode_status
)


class TestLiveTradingGate:
    """Test live trading safety gates."""
    
    def test_paper_mode_always_safe(self):
        """Paper mode should always be safe regardless of env vars."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                "mode": "paper",
                "allow_live_trading": False
            }
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            is_live, mode, reason = check_live_trading_gate(config_path)
            assert not is_live
            assert mode == "paper"
            assert "simulated" in reason.lower() or "paper" in reason.lower()
        finally:
            os.unlink(config_path)
    
    def test_monitor_mode_always_safe(self):
        """Monitor mode should always be safe regardless of env vars."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                "mode": "monitor",
                "allow_live_trading": False
            }
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            is_live, mode, reason = check_live_trading_gate(config_path)
            assert not is_live
            assert mode == "monitor"
            assert "monitor" in reason.lower()
        finally:
            os.unlink(config_path)
    
    def test_live_mode_without_config_flag_blocked(self):
        """Live mode should fail if allow_live_trading is false."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                "mode": "live",
                "allow_live_trading": False
            }
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {"LIVE_TRADING_ENABLED": "true"}):
                is_live, mode, reason = check_live_trading_gate(config_path)
                assert not is_live
                assert mode == "paper"
                assert "allow_live_trading" in reason.lower()
        finally:
            os.unlink(config_path)
    
    def test_live_mode_without_env_var_blocked(self):
        """Live mode should fail if LIVE_TRADING_ENABLED env var is not set."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                "mode": "live",
                "allow_live_trading": True
            }
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {"LIVE_TRADING_ENABLED": "false"}, clear=True):
                is_live, mode, reason = check_live_trading_gate(config_path)
                assert not is_live
                assert mode == "paper"
                assert "environment variable" in reason.lower()
        finally:
            os.unlink(config_path)
    
    def test_live_mode_with_both_gates_passes(self):
        """Live mode should succeed only when both gates pass."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                "mode": "live",
                "allow_live_trading": True
            }
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            with patch.dict(os.environ, {"LIVE_TRADING_ENABLED": "true"}):
                is_live, mode, reason = check_live_trading_gate(config_path)
                assert is_live
                assert mode == "live"
                assert "enabled" in reason.lower()
        finally:
            os.unlink(config_path)
    
    def test_env_var_case_insensitive(self):
        """LIVE_TRADING_ENABLED should accept various true values."""
        test_values = ["true", "True", "TRUE", "yes", "YES", "1"]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                "mode": "live",
                "allow_live_trading": True
            }
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            for val in test_values:
                with patch.dict(os.environ, {"LIVE_TRADING_ENABLED": val}):
                    is_live, mode, reason = check_live_trading_gate(config_path)
                    assert is_live, f"Failed for value: {val}"
                    assert mode == "live", f"Failed for value: {val}"
        finally:
            os.unlink(config_path)
    
    def test_missing_config_defaults_to_paper(self):
        """Missing config file should default to paper mode."""
        is_live, mode, reason = check_live_trading_gate("nonexistent/path.yaml")
        assert not is_live
        assert mode == "paper"
        assert "not found" in reason.lower()
    
    def test_dry_run_requires_gates(self):
        """Dry-run mode should require gates too."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                "mode": "dry_run",
                "allow_live_trading": False
            }
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            # Without gates
            is_live, mode, reason = check_live_trading_gate(config_path)
            assert not is_live
            assert mode == "paper"
            
            # With gates
            with patch.dict(os.environ, {"LIVE_TRADING_ENABLED": "true"}):
                config["allow_live_trading"] = True
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f2:
                    yaml.dump(config, f2)
                    config_path2 = f2.name
                
                try:
                    is_live, mode, reason = check_live_trading_gate(config_path2)
                    assert not is_live  # dry_run without gates still returns false
                    assert mode == "dry_run"
                finally:
                    os.unlink(config_path2)
        finally:
            os.unlink(config_path)


class TestLiveKeyValidation:
    """Test live API key validation."""
    
    def test_no_keys_in_paper_mode_passes(self):
        """Paper mode with no keys should pass."""
        validate_no_live_keys_in_safe_mode(
            api_key=None,
            api_secret=None,
            mode="paper"
        )
        # Should not raise
    
    def test_short_keys_in_paper_mode_passes(self):
        """Paper mode with short/dummy keys should pass."""
        validate_no_live_keys_in_safe_mode(
            api_key="test",
            api_secret="test",
            mode="paper"
        )
        # Should not raise
    
    def test_live_keys_in_paper_mode_fails(self):
        """Paper mode with live-like keys should fail."""
        with pytest.raises(LiveTradingGateError) as exc_info:
            validate_no_live_keys_in_safe_mode(
                api_key="vmPvyjbBx7HjVx7ynXwFvzRNNlkZYxxxxx",  # Real-looking key
                api_secret="hXg0Uo9GfXx0x9XfhX9xfXfXfXfXfXfXfXfXfXfX",  # Real-looking secret
                mode="paper"
            )
        
        assert "Critical safety error" in str(exc_info.value) or "keys detected" in str(exc_info.value).lower()
    
    def test_live_keys_in_monitor_mode_fails(self):
        """Monitor mode with live keys should fail."""
        with pytest.raises(LiveTradingGateError):
            validate_no_live_keys_in_safe_mode(
                api_key="vmPvyjbBx7HjVx7ynXwFvzRNNlkZYxxxxx",
                api_secret="hXg0Uo9GfXx0x9XfhX9xfXfXfXfXfXfXfXfXfXfX",
                mode="monitor"
            )
    
    def test_keys_in_live_mode_passes(self):
        """Live mode should allow keys (gate should have already checked)."""
        validate_no_live_keys_in_safe_mode(
            api_key="vmPvyjbBx7HjVx7ynXwFvzRNNlkZYxxxxx",
            api_secret="hXg0Uo9GfXx0x9XfhX9xfXfXfXfXfXfXfXfXfXfX",
            mode="live"
        )
        # Should not raise


class TestEnforcePaperModeDefault:
    """Test paper mode enforcement."""
    
    def test_enforce_paper_mode_returns_paper(self):
        """Enforce paper mode should always return 'paper'."""
        result = enforce_paper_mode_default()
        assert result == "paper"


class TestLogTradingModeStatus:
    """Test status logging."""
    
    def test_log_live_mode_logs_warning(self, caplog):
        """Live mode should log with warning level."""
        import logging
        caplog.set_level(logging.WARNING)
        
        log_trading_mode_status(True, "live", "Test reason")
        
        assert "LIVE TRADING" in caplog.text or "live" in caplog.text.lower()
    
    def test_log_paper_mode_logs_info(self, caplog):
        """Paper mode should log with info level."""
        import logging
        caplog.set_level(logging.INFO)
        
        log_trading_mode_status(False, "paper", "Test reason")
        
        assert "PAPER" in caplog.text or "paper" in caplog.text.lower()
    
    def test_log_monitor_mode_logs_info(self, caplog):
        """Monitor mode should log with info level."""
        import logging
        caplog.set_level(logging.INFO)
        
        log_trading_mode_status(False, "monitor", "Test reason")
        
        assert "MONITOR" in caplog.text or "monitor" in caplog.text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
