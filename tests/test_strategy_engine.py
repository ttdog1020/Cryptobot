import json
import pathlib
import tempfile
import pandas as pd
import numpy as np
import pytest

from strategy_engine import (
    load_profiles,
    choose_profile,
    load_strategy_profile,
    add_indicators,
    generate_signal_with_profile,
)


@pytest.fixture
def temp_strategy_file():
    """Create a temporary strategy_profiles.json for testing."""
    profiles = {
        "ETH/USDT": {
            "15m": {
                "fast": 8,
                "slow": 26,
                "signal": 7,
                "rsi_buy": 35,
                "rsi_exit": 55,
                "adx_min": 20,
                "trades": 3,
                "win_rate": 100.0,
                "total_pnl": 1.93,
                "final_equity": 5001.93,
            },
            "5m": {
                "fast": 5,
                "slow": 13,
                "signal": 5,
                "rsi_buy": 30,
                "rsi_exit": 70,
                "adx_min": 15,
                "trades": 10,
                "win_rate": 60.0,
                "total_pnl": 5.5,
                "final_equity": 5005.5,
            },
        },
        "BTC/USDT": {
            "1h": {
                "fast": 12,
                "slow": 26,
                "signal": 9,
                "rsi_buy": 40,
                "rsi_exit": 60,
                "adx_min": 22,
                "trades": 5,
                "win_rate": 50.0,
                "total_pnl": 2.0,
                "final_equity": 5002.0,
            },
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir="."
    ) as f:
        json.dump(profiles, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    pathlib.Path(temp_path).unlink(missing_ok=True)


class TestLoadProfiles:
    """Test strategy profile loading functionality."""

    def test_load_profiles_nonexistent_file(self):
        """Should return empty dict for missing file."""
        result = load_profiles("nonexistent_file_xyz.json")
        assert result == {}

    def test_load_profiles_valid_file(self, temp_strategy_file):
        """Should load and return profiles from valid JSON file."""
        result = load_profiles(temp_strategy_file)
        assert isinstance(result, dict)
        assert "ETH/USDT" in result
        assert "BTC/USDT" in result
        assert result["ETH/USDT"]["15m"]["fast"] == 8
        assert result["BTC/USDT"]["1h"]["win_rate"] == 50.0

    def test_load_profiles_invalid_json(self):
        """Should return empty dict for invalid JSON."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir="."
        ) as f:
            f.write("{ invalid json ]")
            temp_path = f.name

        try:
            result = load_profiles(temp_path)
            assert result == {}
        finally:
            pathlib.Path(temp_path).unlink(missing_ok=True)

    def test_load_profiles_non_dict_format(self):
        """Should return empty dict if root is not a dict."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir="."
        ) as f:
            json.dump(["not", "a", "dict"], f)
            temp_path = f.name

        try:
            result = load_profiles(temp_path)
            assert result == {}
        finally:
            pathlib.Path(temp_path).unlink(missing_ok=True)


class TestChooseProfile:
    """Test profile selection and fallback logic."""

    def test_choose_profile_prefers_specified_symbol_timeframe(
        self, temp_strategy_file, monkeypatch
    ):
        """Should prefer specified symbol+timeframe when available."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", temp_strategy_file)

        symbol, timeframe, cfg = choose_profile(
            preferred_symbol="ETH/USDT", preferred_timeframe="15m"
        )
        assert symbol == "ETH/USDT"
        assert timeframe == "15m"
        assert cfg["fast"] == 8

    def test_choose_profile_fallback_to_best_on_missing_preferred(
        self, temp_strategy_file, monkeypatch
    ):
        """Should fallback to best profile if preferred not found."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", temp_strategy_file)

        symbol, timeframe, cfg = choose_profile(
            preferred_symbol="NONEXISTENT", preferred_timeframe="999m"
        )
        # Should find the best: ETH/USDT 15m has win_rate 100.0 (highest)
        assert symbol == "ETH/USDT"
        assert timeframe == "15m"
        assert cfg["win_rate"] == 100.0

    def test_choose_profile_scoring_by_win_rate_then_pnl(
        self, temp_strategy_file, monkeypatch
    ):
        """Should score profiles by win_rate first, then total_pnl."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", temp_strategy_file)

        symbol, timeframe, cfg = choose_profile()
        # ETH/USDT 15m: win_rate=100.0, pnl=1.93
        # ETH/USDT 5m:  win_rate=60.0, pnl=5.5
        # BTC/USDT 1h:   win_rate=50.0, pnl=2.0
        # Should pick ETH/USDT 15m (highest win_rate)
        assert cfg["win_rate"] == 100.0

    def test_choose_profile_empty_profiles(self, monkeypatch):
        """Should handle empty profiles gracefully."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", "nonexistent.json")

        symbol, timeframe, cfg = choose_profile()
        assert symbol is None
        assert timeframe is None
        assert cfg == {}


class TestLoadStrategyProfile:
    """Test specific profile loading."""

    def test_load_strategy_profile_exists(self, temp_strategy_file, monkeypatch):
        """Should return profile dict for valid symbol+timeframe."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", temp_strategy_file)

        profile = load_strategy_profile("ETH/USDT", "15m")
        assert profile is not None
        assert profile["fast"] == 8
        assert profile["win_rate"] == 100.0

    def test_load_strategy_profile_nonexistent_symbol(
        self, temp_strategy_file, monkeypatch
    ):
        """Should return None for nonexistent symbol."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", temp_strategy_file)

        profile = load_strategy_profile("NONEXISTENT/USDT", "15m")
        assert profile is None

    def test_load_strategy_profile_nonexistent_timeframe(
        self, temp_strategy_file, monkeypatch
    ):
        """Should return None for nonexistent timeframe."""
        monkeypatch.setattr("strategy_engine.DEFAULT_PATH", temp_strategy_file)

        profile = load_strategy_profile("ETH/USDT", "999m")
        assert profile is None


class TestAddIndicators:
    """Test indicator addition wrapper."""

    def test_add_indicators_returns_dataframe(self):
        """Should return a DataFrame with indicators added."""
        df = pd.DataFrame(
            {
                "open": [100.0] * 50,
                "high": [101.0] * 50,
                "low": [99.0] * 50,
                "close": [100.0] * 50,
                "volume": [1000.0] * 50,
            }
        )

        result = add_indicators(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 50

    def test_add_indicators_with_empty_params(self):
        """Should handle empty params dict."""
        df = pd.DataFrame(
            {
                "open": [100.0] * 50,
                "high": [101.0] * 50,
                "low": [99.0] * 50,
                "close": [100.0] * 50,
                "volume": [1000.0] * 50,
            }
        )

        result = add_indicators(df, params={})
        assert isinstance(result, pd.DataFrame)


class TestGenerateSignalWithProfile:
    """Test signal generation with bar_index."""

    def test_generate_signal_with_valid_bar_index(self):
        """Should return a signal string for valid bar_index."""
        df = pd.DataFrame(
            {
                "open": [100.0 + i * 0.1 for i in range(50)],
                "high": [101.0 + i * 0.1 for i in range(50)],
                "low": [99.0 + i * 0.1 for i in range(50)],
                "close": [100.0 + i * 0.1 for i in range(50)],
                "volume": [1000.0] * 50,
            }
        )

        signal = generate_signal_with_profile(df, bar_index=25)
        assert signal in ["LONG", "SHORT", "HOLD"]

    def test_generate_signal_with_negative_bar_index(self):
        """Should return HOLD for negative bar_index."""
        df = pd.DataFrame(
            {
                "close": [100.0] * 50,
            }
        )

        signal = generate_signal_with_profile(df, bar_index=-1)
        assert signal == "HOLD"

    def test_generate_signal_with_out_of_bounds_bar_index(self):
        """Should return HOLD for out-of-bounds bar_index."""
        df = pd.DataFrame(
            {
                "close": [100.0] * 50,
            }
        )

        signal = generate_signal_with_profile(df, bar_index=100)
        assert signal == "HOLD"

    def test_generate_signal_with_params(self):
        """Should accept params and return a signal."""
        df = pd.DataFrame(
            {
                "open": [100.0 + i * 0.1 for i in range(50)],
                "high": [101.0 + i * 0.1 for i in range(50)],
                "low": [99.0 + i * 0.1 for i in range(50)],
                "close": [100.0 + i * 0.1 for i in range(50)],
                "volume": [1000.0] * 50,
            }
        )

        signal = generate_signal_with_profile(
            df, bar_index=25, params={"rsi_buy": 30}
        )
        assert signal in ["LONG", "SHORT", "HOLD"]
