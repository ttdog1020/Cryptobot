import pandas as pd
import numpy as np
import pytest

from regime_engine import classify_regime, detect_regime, get_regime_summary


def _base_frame(length: int) -> pd.DataFrame:
    """Construct a base DataFrame with safe defaults for regime detection."""
    close = np.full(length, 100.0)
    ema_fast = np.full(length, 100.0)
    ema_slow = np.full(length, 100.0)
    adx = np.full(length, 10.0)
    atr = np.full(length, 1.0)
    high = close + 0.2
    low = close - 0.2

    return pd.DataFrame(
        {
            "close": close,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "adx": adx,
            "atr": atr,
            "high": high,
            "low": low,
        }
    )


def test_detect_regime_neutral_when_insufficient_data() -> None:
    df = _base_frame(10)

    assert detect_regime(df) == "NEUTRAL"
    assert detect_regime(None) == "NEUTRAL"


def test_detect_trending_regime_uptrend() -> None:
    df = _base_frame(25)
    df.loc[:, "close"] = 102.0
    df.loc[:, "ema_fast"] = 101.0
    df.loc[:, "ema_slow"] = 100.0
    df.loc[:, "adx"] = 30.0
    df.loc[:, "high"] = 102.2
    df.loc[:, "low"] = 101.8

    assert detect_regime(df) == "TRENDING"


def test_detect_ranging_regime_with_decreasing_atr() -> None:
    df = _base_frame(25)
    df.loc[:, "close"] = 100.0
    df.loc[:, "ema_fast"] = 100.05
    df.loc[:, "ema_slow"] = 100.0
    df.loc[:, "adx"] = 12.0
    df.loc[:, "atr"] = 1.0
    df.loc[20:24, "atr"] = [1.0, 1.0, 1.0, 1.0, 0.7]
    df.loc[:, "high"] = 100.2
    df.loc[:, "low"] = 99.8

    assert detect_regime(df) == "RANGING"


def test_detect_breakout_regime_on_atr_increase() -> None:
    df = _base_frame(25)
    df.loc[:, "close"] = 103.0
    df.loc[:, "ema_fast"] = 101.0
    df.loc[:, "ema_slow"] = 100.0
    df.loc[:, "adx"] = 15.0
    df.loc[:, "atr"] = 1.0
    df.loc[24, "atr"] = 1.25
    df.loc[:, "high"] = 103.5
    df.loc[:, "low"] = 102.5

    assert detect_regime(df) == "BREAKOUT"


def test_classify_regime_requires_lookback() -> None:
    df = _base_frame(25)
    df.loc[:, "close"] = 102.0
    df.loc[:, "ema_fast"] = 101.0
    df.loc[:, "ema_slow"] = 100.0
    df.loc[:, "adx"] = 30.0

    assert classify_regime(df, lookback=30) == "NEUTRAL"
    assert classify_regime(df, lookback=20) == "TRENDING"


def test_get_regime_summary_counts_and_percentages() -> None:
    df = _base_frame(30)

    # TRENDING segment
    df.loc[18:24, "close"] = 102.0
    df.loc[18:24, "ema_fast"] = 101.0
    df.loc[18:24, "ema_slow"] = 100.0
    df.loc[18:24, "adx"] = 28.0
    df.loc[18:24, "atr"] = 1.0
    df.loc[18:24, "high"] = 102.2
    df.loc[18:24, "low"] = 101.8

    # RANGING segment
    df.loc[25:27, "close"] = 100.0
    df.loc[25:27, "ema_fast"] = 100.05
    df.loc[25:27, "ema_slow"] = 100.0
    df.loc[25:27, "adx"] = 10.0
    df.loc[25:27, "atr"] = 0.7
    df.loc[25:27, "high"] = 100.2
    df.loc[25:27, "low"] = 99.8

    # BREAKOUT segment
    df.loc[28:29, "close"] = 103.0
    df.loc[28:29, "ema_fast"] = 101.0
    df.loc[28:29, "ema_slow"] = 100.0
    df.loc[28:29, "adx"] = 15.0
    df.loc[28:29, "atr"] = 1.3
    df.loc[28:29, "high"] = 103.5
    df.loc[28:29, "low"] = 102.5

    summary = get_regime_summary(df, start_index=20)

    assert summary["TRENDING"]["count"] == 5
    assert summary["RANGING"]["count"] == 3
    assert summary["BREAKOUT"]["count"] == 2
    assert pytest.approx(summary["TRENDING"]["percentage"], rel=1e-3) == 50.0
    assert pytest.approx(summary["RANGING"]["percentage"], rel=1e-3) == 30.0
    assert pytest.approx(summary["BREAKOUT"]["percentage"], rel=1e-3) == 20.0
