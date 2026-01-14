import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import tempfile
import csv

from bot import (
    BotConfig,
    PaperTrader,
    ensure_logs_exist,
    _fmt_usd,
    _fmt_size,
    log_trade,
    log_equity,
    log_risk_event,
)
from risk_management import RiskConfig


class TestBotConfig:
    """Test legacy BotConfig dataclass."""

    def test_bot_config_has_all_required_fields(self):
        """Should have all required configuration fields."""
        config = BotConfig()
        
        assert hasattr(config, "exchange")
        assert hasattr(config, "symbol")
        assert hasattr(config, "timeframe")
        assert hasattr(config, "starting_balance")
        assert hasattr(config, "risk_per_trade_pct")
        assert hasattr(config, "max_drawdown_pct")
        assert hasattr(config, "trader_mode")

    def test_bot_config_numeric_values_valid(self):
        """Should have valid numeric values."""
        config = BotConfig()
        
        assert isinstance(config.starting_balance, float)
        assert config.starting_balance > 0
        assert isinstance(config.risk_per_trade_pct, float)
        assert config.risk_per_trade_pct > 0
        assert isinstance(config.max_drawdown_pct, float)

    def test_bot_config_string_values_valid(self):
        """Should have valid string values."""
        config = BotConfig()
        
        assert isinstance(config.exchange, str)
        assert len(config.exchange) > 0
        assert isinstance(config.symbol, str)
        assert "/" in config.symbol  # Expect pair format
        assert isinstance(config.timeframe, str)
        assert len(config.timeframe) > 0


class TestFormatting:
    """Test formatting utility functions."""

    def test_fmt_usd_formats_to_two_decimals(self):
        """Should format USD values to 2 decimals."""
        assert _fmt_usd(100.0) == "100.00"
        assert _fmt_usd(100.1234) == "100.12"
        assert _fmt_usd(0.999) == "1.00"

    def test_fmt_usd_handles_invalid_input(self):
        """Should handle non-numeric input gracefully."""
        result = _fmt_usd("invalid")
        assert result == "invalid"

    def test_fmt_size_formats_to_eight_decimals(self):
        """Should format size values to 8 decimals."""
        assert _fmt_size(0.1) == "0.10000000"
        assert _fmt_size(0.12345678) == "0.12345678"
        assert _fmt_size(1.0) == "1.00000000"

    def test_fmt_size_handles_invalid_input(self):
        """Should handle non-numeric input gracefully."""
        result = _fmt_size("invalid")
        assert result == "invalid"


class TestLogging:
    """Test logging functions."""

    def test_ensure_logs_exist_creates_files(self, tmp_path, monkeypatch):
        """Should create log files with proper headers."""
        log_dir = tmp_path / "logs"
        trades_log = log_dir / "trades.csv"
        equity_log = log_dir / "equity.csv"
        risk_log = log_dir / "risk_events.csv"
        
        monkeypatch.setattr("bot.LOG_DIR", log_dir)
        monkeypatch.setattr("bot.TRADES_LOG", trades_log)
        monkeypatch.setattr("bot.EQUITY_LOG", equity_log)
        monkeypatch.setattr("bot.RISK_LOG", risk_log)
        
        ensure_logs_exist()
        
        assert trades_log.exists()
        assert equity_log.exists()
        assert risk_log.exists()

    def test_log_trade_writes_to_csv(self, tmp_path, monkeypatch):
        """Should write trade data to trades.csv."""
        log_dir = tmp_path / "logs"
        trades_log = log_dir / "trades.csv"
        
        monkeypatch.setattr("bot.LOG_DIR", log_dir)
        monkeypatch.setattr("bot.TRADES_LOG", trades_log)
        monkeypatch.setattr("bot.EQUITY_LOG", log_dir / "equity.csv")
        monkeypatch.setattr("bot.RISK_LOG", log_dir / "risk_events.csv")
        
        ensure_logs_exist()
        
        ts = datetime.now(timezone.utc).isoformat()
        log_trade(ts, "OPEN_LONG", 100.0, 0.1, 0.0, 1000.0, 
                  stop_loss=99.0, take_profit=105.0, atr=0.5)
        
        # Verify data was written
        with open(trades_log) as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 2  # header + 1 trade
            assert rows[1][1] == "OPEN_LONG"
            assert rows[1][2] == "100.00"  # USD formatting

    def test_log_equity_writes_to_csv(self, tmp_path, monkeypatch):
        """Should write equity data to equity.csv."""
        log_dir = tmp_path / "logs"
        equity_log = log_dir / "equity.csv"
        
        monkeypatch.setattr("bot.LOG_DIR", log_dir)
        monkeypatch.setattr("bot.TRADES_LOG", log_dir / "trades.csv")
        monkeypatch.setattr("bot.EQUITY_LOG", equity_log)
        monkeypatch.setattr("bot.RISK_LOG", log_dir / "risk_events.csv")
        
        ensure_logs_exist()
        
        ts = datetime.now(timezone.utc).isoformat()
        log_equity(ts, 1000.0)
        
        # Verify data was written
        with open(equity_log) as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 2  # header + 1 equity entry

    def test_log_risk_event_writes_to_csv(self, tmp_path, monkeypatch):
        """Should write risk events to risk_events.csv."""
        log_dir = tmp_path / "logs"
        risk_log = log_dir / "risk_events.csv"
        
        monkeypatch.setattr("bot.LOG_DIR", log_dir)
        monkeypatch.setattr("bot.TRADES_LOG", log_dir / "trades.csv")
        monkeypatch.setattr("bot.EQUITY_LOG", log_dir / "equity.csv")
        monkeypatch.setattr("bot.RISK_LOG", risk_log)
        
        ensure_logs_exist()
        
        ts = datetime.now(timezone.utc).isoformat()
        log_risk_event(ts, "MAX_DRAWDOWN", "Exceeded 10%", 950.0)
        
        # Verify data was written
        with open(risk_log) as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 2  # header + 1 risk event


class TestPaperTrader:
    """Test legacy PaperTrader class."""

    def test_paper_trader_initialization(self):
        """Should initialize with balance and empty position."""
        trader = PaperTrader(balance=1000.0)
        
        assert trader.balance == 1000.0
        assert trader.position_size == 0.0
        assert trader.entry_price == 0.0
        assert trader.position_side is None
        assert trader.closed_trade_pnls == []

    def test_paper_trader_with_strategy_profile(self):
        """Should load risk parameters from strategy profile."""
        profile = {
            "risk_per_trade_pct": 2.0,
            "sl_atr_mult": 2.0,
            "tp_atr_mult": 4.0,
            "min_position_size_usd": 20.0,
        }
        
        trader = PaperTrader(balance=1000.0, strategy_profile=profile)
        
        assert trader.risk_pct == 0.02
        assert trader.sl_mult == 2.0
        assert trader.tp_mult == 4.0

    def test_paper_trader_open_long_requires_atr(self):
        """Should reject LONG open without valid ATR."""
        trader = PaperTrader(balance=1000.0)
        
        # Should not open position without ATR
        trader.open_long(price=100.0, atr=None)
        
        assert trader.position_side is None

    def test_paper_trader_open_long_with_valid_atr(self, tmp_path, monkeypatch):
        """Should open LONG position with valid ATR."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("bot.LOG_DIR", log_dir)
        monkeypatch.setattr("bot.TRADES_LOG", log_dir / "trades.csv")
        monkeypatch.setattr("bot.EQUITY_LOG", log_dir / "equity.csv")
        monkeypatch.setattr("bot.RISK_LOG", log_dir / "risk_events.csv")
        
        ensure_logs_exist()
        
        trader = PaperTrader(balance=1000.0)
        trader.open_long(price=100.0, atr=1.0)
        
        assert trader.position_side == "LONG"
        assert trader.entry_price == 100.0
        assert trader.position_size > 0

    def test_paper_trader_close_long_position(self, tmp_path, monkeypatch):
        """Should close LONG position and calculate PnL."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("bot.LOG_DIR", log_dir)
        monkeypatch.setattr("bot.TRADES_LOG", log_dir / "trades.csv")
        monkeypatch.setattr("bot.EQUITY_LOG", log_dir / "equity.csv")
        monkeypatch.setattr("bot.RISK_LOG", log_dir / "risk_events.csv")
        
        ensure_logs_exist()
        
        trader = PaperTrader(balance=1000.0)
        trader.open_long(price=100.0, atr=1.0)
        
        initial_balance = trader.balance
        trader.close_position(price=105.0)
        
        assert trader.position_side is None
        assert trader.balance > initial_balance  # Positive PnL

    def test_paper_trader_warns_on_duplicate_long(self, tmp_path, monkeypatch):
        """Should warn if attempting to open LONG while already in LONG."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("bot.LOG_DIR", log_dir)
        monkeypatch.setattr("bot.TRADES_LOG", log_dir / "trades.csv")
        monkeypatch.setattr("bot.EQUITY_LOG", log_dir / "equity.csv")
        monkeypatch.setattr("bot.RISK_LOG", log_dir / "risk_events.csv")
        
        ensure_logs_exist()
        
        trader = PaperTrader(balance=1000.0)
        trader.open_long(price=100.0, atr=1.0)
        
        # Attempt to open another LONG (should be rejected)
        trader.open_long(price=101.0, atr=1.0)
        
        # Position should remain unchanged
        assert trader.entry_price == 100.0

    def test_paper_trader_warns_on_close_without_position(self):
        """Should warn if attempting to close without open position."""
        trader = PaperTrader(balance=1000.0)
        
        # Close without position should not crash
        trader.close_position(price=100.0)
        
        assert trader.position_side is None
        assert trader.balance == 1000.0  # Balance unchanged


class TestPaperTraderEdgeCases:
    """Test edge cases and error handling."""

    def test_paper_trader_handles_zero_balance(self):
        """Should handle zero balance gracefully."""
        trader = PaperTrader(balance=0.0)
        
        assert trader.balance == 0.0

    def test_paper_trader_handles_negative_balance(self):
        """Should allow negative balance (represents loss)."""
        trader = PaperTrader(balance=-100.0)
        
        assert trader.balance == -100.0

    def test_paper_trader_equity_curve_tracks_balance(self, tmp_path, monkeypatch):
        """Should maintain equity curve."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("bot.LOG_DIR", log_dir)
        monkeypatch.setattr("bot.TRADES_LOG", log_dir / "trades.csv")
        monkeypatch.setattr("bot.EQUITY_LOG", log_dir / "equity.csv")
        monkeypatch.setattr("bot.RISK_LOG", log_dir / "risk_events.csv")
        
        ensure_logs_exist()
        
        trader = PaperTrader(balance=1000.0)
        
        assert isinstance(trader.equity_curve, list)
