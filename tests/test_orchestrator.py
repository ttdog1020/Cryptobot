import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from orchestrator import SymbolController, ensure_multi_trades_log, ensure_multi_equity_log


@pytest.fixture
def sample_ohlcv_dataframe():
    """Create a sample OHLCV dataframe with indicators."""
    n = 100
    close = np.linspace(100, 110, n)
    
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="1H"),
        "open": close - 0.5,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": np.full(n, 1000.0),
    })
    
    # Add technical indicators
    df["ema_fast"] = df["close"].ewm(span=12).mean()
    df["ema_slow"] = df["close"].ewm(span=26).mean()
    df["atr"] = np.full(n, 0.5)
    df["adx"] = np.linspace(10, 30, n)
    df["rsi"] = np.linspace(30, 70, n)
    
    return df


@pytest.fixture
def mock_exchange():
    """Mock exchange object."""
    class MockExchange:
        def fetch_ohlcv(self, symbol, timeframe, limit=500):
            return []
    
    return MockExchange()


@pytest.fixture
def temp_symbol_config(tmp_path):
    """Create temporary symbol config directory."""
    import json
    
    config = {
        "ETH/USDT": {
            "15m": {
                "fast": 8,
                "slow": 26,
                "signal": 7,
                "rsi_buy": 35,
                "rsi_exit": 55,
                "adx_min": 20,
                "risk_per_trade_pct": 1.0,
                "sl_atr_mult": 1.5,
                "tp_atr_mult": 3.0,
                "min_position_size_usd": 10.0,
            }
        }
    }
    
    config_path = tmp_path / "strategy_profiles.json"
    with open(config_path, "w") as f:
        json.dump(config, f)
    
    return config_path


class TestSymbolController:
    """Test SymbolController state management and trading logic."""

    def test_symbol_controller_initialization(self, temp_symbol_config, monkeypatch):
        """Should initialize with balance, symbol, and timeframe."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", str(temp_symbol_config))
        
        controller = SymbolController("ETH/USDT", "15m", starting_balance=1000.0)
        
        assert controller.symbol == "ETH/USDT"
        assert controller.timeframe == "15m"
        assert controller.trader.balance == 1000.0
        assert controller.current_regime == "DEFAULT"

    def test_symbol_controller_loads_profile(self, temp_symbol_config, monkeypatch):
        """Should load strategy profile from strategy_profiles.json."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", str(temp_symbol_config))
        
        controller = SymbolController("ETH/USDT", "15m", starting_balance=1000.0)
        
        assert controller.profile is not None
        assert controller.profile["fast"] == 8
        assert controller.profile["rsi_buy"] == 35

    def test_symbol_controller_missing_profile_defaults(self, temp_symbol_config, monkeypatch):
        """Should use default empty profile if symbol not found."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", str(temp_symbol_config))
        
        controller = SymbolController("UNKNOWN/USDT", "15m", starting_balance=1000.0)
        
        assert controller.profile == {}
        assert controller.active_profile == {}

    def test_update_strategy_profile_refreshes_trader(self, temp_symbol_config, monkeypatch):
        """Should update profile and refresh trader parameters."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", str(temp_symbol_config))
        
        controller = SymbolController("ETH/USDT", "15m", starting_balance=1000.0)
        new_profile = {
            "fast": 10,
            "slow": 30,
            "signal": 8,
            "rsi_buy": 40,
            "risk_per_trade_pct": 2.0,
            "sl_atr_mult": 2.0,
            "tp_atr_mult": 4.0,
            "min_position_size_usd": 20.0,
        }
        
        controller.update_strategy_profile(new_profile)
        
        assert controller.profile["fast"] == 10
        assert controller.trader.risk_pct == 2.0
        assert controller.trader.sl_mult == 2.0

    def test_select_profile_for_regime_default(self, temp_symbol_config, monkeypatch):
        """Should keep base profile when regime is DEFAULT."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", str(temp_symbol_config))
        
        controller = SymbolController("ETH/USDT", "15m", starting_balance=1000.0)
        base_profile = dict(controller.active_profile)
        
        controller.select_profile_for_regime("DEFAULT")
        
        assert controller.current_regime == "DEFAULT"
        assert controller.active_profile == base_profile

    def test_select_profile_for_regime_no_overrides(self, temp_symbol_config, monkeypatch):
        """Should return early if no regime overrides defined."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", str(temp_symbol_config))
        
        controller = SymbolController("ETH/USDT", "15m", starting_balance=1000.0)
        controller.regime_profiles = {}  # No overrides
        
        controller.select_profile_for_regime("TRENDING")
        
        assert controller.current_regime == "DEFAULT"  # Should not change

    def test_select_profile_for_regime_with_overrides(self, temp_symbol_config, monkeypatch):
        """Should apply regime-specific overrides."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", str(temp_symbol_config))
        
        controller = SymbolController("ETH/USDT", "15m", starting_balance=1000.0)
        controller.regime_profiles = {
            "TRENDING": {
                "rsi_buy": 40,
                "adx_min": 25,
            }
        }
        
        controller.select_profile_for_regime("TRENDING")
        
        assert controller.current_regime == "TRENDING"
        assert controller.active_profile["rsi_buy"] == 40
        assert controller.active_profile["adx_min"] == 25

    def test_run_cycle_skips_warmup(self, sample_ohlcv_dataframe, temp_symbol_config, monkeypatch):
        """Should skip cycle if bar_index < 30 (warmup period)."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", str(temp_symbol_config))
        
        controller = SymbolController("ETH/USDT", "15m", starting_balance=1000.0)
        trades = controller.run_cycle(sample_ohlcv_dataframe, bar_index=10)
        
        assert trades == []

    def test_run_cycle_after_warmup(self, sample_ohlcv_dataframe, temp_symbol_config, monkeypatch):
        """Should process cycle after warmup period."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", str(temp_symbol_config))
        
        controller = SymbolController("ETH/USDT", "15m", starting_balance=1000.0)
        trades = controller.run_cycle(sample_ohlcv_dataframe, bar_index=35)
        
        # Should return list (may be empty if no trades triggered)
        assert isinstance(trades, list)

    def test_run_cycle_with_long_position_and_tp_hit(self, sample_ohlcv_dataframe, temp_symbol_config, monkeypatch):
        """Should close LONG position when TP is hit."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", str(temp_symbol_config))
        
        controller = SymbolController("ETH/USDT", "15m", starting_balance=1000.0)
        
        # Manually set up a LONG position
        controller.trader.position_side = "LONG"
        controller.trader.position_size = 0.1
        controller.trader.entry_price = 100.0
        controller.trader.stop_loss = 99.0
        controller.trader.take_profit = 105.0
        controller.trader.current_atr = 0.5
        
        # Set high to exceed TP
        sample_ohlcv_dataframe.loc[35, "high"] = 106.0
        
        trades = controller.run_cycle(sample_ohlcv_dataframe, bar_index=35)
        
        # Position should be closed
        assert controller.trader.position_side is None
        assert len(trades) > 0

    def test_fetch_data_no_exchange(self, temp_symbol_config, monkeypatch):
        """Should return None if no exchange is set."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", str(temp_symbol_config))
        
        controller = SymbolController("ETH/USDT", "15m", starting_balance=1000.0, exchange=None)
        data = controller.fetch_data()
        
        assert data is None


class TestOrchestratorLogging:
    """Test multi-symbol logging functions."""

    def test_ensure_multi_trades_log_creates_file(self, tmp_path, monkeypatch):
        """Should create trades_multi.csv with proper header."""
        log_dir = tmp_path / "logs"
        log_path = log_dir / "trades_multi.csv"
        
        monkeypatch.setattr("orchestrator.MULTI_TRADES_LOG", log_path)
        
        ensure_multi_trades_log()
        
        assert log_path.exists()
        
        # Check header
        with open(log_path) as f:
            header = f.readline().strip()
            assert "symbol" in header
            assert "regime" in header

    def test_ensure_multi_equity_log_creates_file(self, tmp_path, monkeypatch):
        """Should create equity_multi.csv with proper header."""
        log_dir = tmp_path / "logs"
        log_path = log_dir / "equity_multi.csv"
        
        monkeypatch.setattr("orchestrator.MULTI_EQUITY_LOG", log_path)
        
        ensure_multi_equity_log()
        
        assert log_path.exists()
        
        # Check header
        with open(log_path) as f:
            header = f.readline().strip()
            assert "symbol" in header
            assert "equity" in header
