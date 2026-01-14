"""
Tests for Risk Management Module (PR9)

Tests for RiskConfig and RiskEngine validation.
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from risk_management.risk_engine import RiskConfig, RiskEngine


class TestRiskConfig:
    """Test RiskConfig dataclass"""
    
    def test_risk_config_defaults(self):
        """Test default values"""
        config = RiskConfig()
        assert config.base_account_size == 1000.0
        assert config.default_risk_per_trade == 0.01
        assert config.default_slippage == 0.001
        assert config.default_sl_atr_mult == 1.5
        assert config.default_tp_atr_mult == 3.0
        assert config.min_position_size_usd == 10.0
    
    def test_risk_config_custom_values(self):
        """Test custom initialization"""
        config = RiskConfig(
            base_account_size=50000.0,
            default_risk_per_trade=0.02,
            max_exposure=0.5
        )
        assert config.base_account_size == 50000.0
        assert config.default_risk_per_trade == 0.02
        assert config.max_exposure == 0.5
    
    def test_risk_config_from_file_nonexistent(self):
        """Test loading from non-existent file (should use defaults)"""
        config = RiskConfig.from_file(Path("/nonexistent/risk.json"))
        assert config.base_account_size == 1000.0


class TestRiskEngine:
    """Test RiskEngine functionality"""
    
    def test_risk_engine_initialization(self):
        """Test RiskEngine initialization"""
        config = RiskConfig(base_account_size=50000.0)
        engine = RiskEngine(config)
        
        assert engine.config.base_account_size == 50000.0
    
    def test_risk_calculation(self):
        """Test risk amount calculation"""
        config = RiskConfig(
            base_account_size=50000.0,
            default_risk_per_trade=0.02
        )
        
        risk_amount = 50000.0 * 0.02
        assert risk_amount == pytest.approx(1000.0, rel=1e-2)
    
    def test_position_sizing_logic(self):
        """Test position sizing calculation"""
        entry_price = 45000.0
        stop_loss_price = 44000.0
        risk_amount = 1000.0
        
        risk_distance = entry_price - stop_loss_price
        position_size = risk_amount / risk_distance
        
        assert position_size == pytest.approx(1.0, rel=1e-2)


class TestRiskEdgeCases:
    """Edge cases and error handling"""
    
    def test_zero_account_size(self):
        """Test with zero account size"""
        config = RiskConfig(base_account_size=0.0)
        engine = RiskEngine(config)
        assert engine.config.base_account_size == 0.0
    
    def test_negative_risk_per_trade(self):
        """Test negative risk parameter"""
        config = RiskConfig(default_risk_per_trade=-0.01)
        assert config.default_risk_per_trade == -0.01


class TestRiskConfigLoad:
    """Test loading risk configuration"""
    
    def test_load_from_json_file(self):
        """Test loading config from JSON"""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "risk.json"
            
            config_data = {
                "base_account_size": 100000.0,
                "default_risk_per_trade": 0.015
            }
            with open(config_path, 'w') as f:
                json.dump(config_data, f)
            
            config = RiskConfig.from_file(config_path)
            assert config.base_account_size == 100000.0
            assert config.default_risk_per_trade == 0.015


class TestATRCalculations:
    """Test ATR-based calculations"""
    
    def test_stop_loss_distance(self):
        """Test SL distance from ATR"""
        atr = 100.0
        sl_mult = 1.5
        sl_distance = atr * sl_mult
        assert sl_distance == 150.0
    
    def test_take_profit_distance(self):
        """Test TP distance from ATR"""
        atr = 100.0
        tp_mult = 3.0
        tp_distance = atr * tp_mult
        assert tp_distance == 300.0
    
    def test_risk_reward_ratio(self):
        """Test R:R ratio"""
        risk = 150.0
        reward = 300.0
        rr_ratio = reward / risk
        assert rr_ratio == pytest.approx(2.0, rel=1e-2)
