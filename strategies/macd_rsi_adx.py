import pandas as pd
import numpy as np
from ta.trend import MACD, ADXIndicator
from ta.momentum import RSIIndicator
from typing import Optional, Dict, Any


def add_indicators_macd_rsi_adx(
    df: pd.DataFrame,
    params: Optional[Dict[str, Any]] = None,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    trend_ema_fast: int = 20,
    trend_ema_slow: int = 50
) -> pd.DataFrame:
    """
    Add MACD, RSI, ADX, and trend EMA indicators to the dataframe.
    
    Args:
        df: DataFrame with OHLCV data
        params: Optional dict with 'fast', 'slow', 'signal', 'trend_ema_fast', 'trend_ema_slow' keys
        fast: MACD fast period (default 12)
        slow: MACD slow period (default 26)
        signal: MACD signal period (default 9)
        trend_ema_fast: Trend filter fast EMA period (default 20)
        trend_ema_slow: Trend filter slow EMA period (default 50)
    
    Returns:
        DataFrame with indicators added
    """
    # If params dict is provided, extract values from it
    if params is not None:
        fast = int(params.get("fast", fast))
        slow = int(params.get("slow", slow))
        signal = int(params.get("signal", signal))
        trend_ema_fast = int(params.get("trend_ema_fast", trend_ema_fast))
        trend_ema_slow = int(params.get("trend_ema_slow", trend_ema_slow))
    
    df = df.copy()
    
    # Ensure numeric
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    close = df["close"]
    high = df["high"]
    low = df["low"]
    
    # MACD
    macd_indicator = MACD(close=close, window_slow=slow, window_fast=fast, window_sign=signal)
    df["macd"] = macd_indicator.macd()
    df["macd_signal"] = macd_indicator.macd_signal()
    df["macd_diff"] = macd_indicator.macd_diff()
    
    # RSI (14-period default in ta library)
    rsi_indicator = RSIIndicator(close=close, window=14)
    df["rsi"] = rsi_indicator.rsi()
    
    # ADX (14-period default in ta library)
    adx_indicator = ADXIndicator(high=high, low=low, close=close, window=14)
    df["adx"] = adx_indicator.adx()
    
    # ATR for stop-loss/take-profit
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = tr.rolling(window=14).mean()
    
    # Trend filter EMAs (pseudo-MTF)
    df["trend_ema_fast"] = close.ewm(span=trend_ema_fast, adjust=False).mean()
    df["trend_ema_slow"] = close.ewm(span=trend_ema_slow, adjust=False).mean()
    
    # Soft trend confirmation: is fast EMA rising?
    df["trend_fast_rising"] = df["trend_ema_fast"].diff() > 0
    
    # Softer confirmation: was fast EMA rising in the last 3 bars?
    df["trend_fast_rising_3"] = df["trend_ema_fast"].diff().rolling(3).sum() > 0
    
    # ========== MODULE 4: ADVANCED ENTRY INDICATORS ==========
    
    # 1) ATR as percentage of close price (volatility measure)
    df["atr_pct"] = df["atr"] / close
    
    # 2) Directional Indicators (DI+, DI-) and their difference
    atr_period = params.get("atr_period", 14) if params else 14
    adx_ind = ADXIndicator(high=high, low=low, close=close, window=atr_period)
    df["di_plus"] = adx_ind.adx_pos()
    df["di_minus"] = adx_ind.adx_neg()
    df["di_diff"] = df["di_plus"] - df["di_minus"]
    
    # 3) MACD histogram and its slope (momentum confirmation)
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    macd_hist_lookback = params.get("macd_hist_lookback", 3) if params else 3
    df["macd_hist_slope"] = df["macd_hist"].diff(macd_hist_lookback)
    
    # 4) RSI momentum (rising RSI from oversold)
    rsi_mom_lookback = params.get("rsi_mom_lookback", 3) if params else 3
    df["rsi_mom"] = df["rsi"].diff(rsi_mom_lookback)
    
    return df


def generate_signal_macd_rsi_adx(
    df: pd.DataFrame,
    params: Optional[Dict[str, Any]] = None,
    rsi_buy: float = 35.0,
    rsi_exit: float = 55.0,
    adx_min: float = 20.0
) -> str:
    """
    Generate trading signal based on MACD, RSI, ADX, and trend EMAs.
    MODULE 4: Enhanced with ATR volatility, DI+/DI-, MACD histogram momentum, RSI momentum.
    
    Args:
        df: DataFrame with indicators
        params: Optional dict with all parameter keys (overrides individual params)
        rsi_buy: RSI threshold for buy signals (default 35.0)
        rsi_exit: RSI threshold for exit signals (default 55.0)
        adx_min: Minimum ADX for trend strength filter (default 20.0)
    
    Returns:
        "BUY", "SELL", or "HOLD"
    """
    # If params dict is provided, extract values from it
    if params is not None:
        rsi_buy = float(params.get("rsi_buy", rsi_buy))
        rsi_exit = float(params.get("rsi_exit", rsi_exit))
        adx_min = float(params.get("adx_min", adx_min))
        # Module 4 params
        atr_vol_thresh = float(params.get("atr_vol_thresh", 0.0015))
        di_margin = float(params.get("di_margin", 2.0))
    else:
        atr_vol_thresh = 0.0015
        di_margin = 2.0
    
    if df.empty or len(df) < 2:
        return "HOLD"
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Check required columns
    required = ["macd", "macd_signal", "rsi", "adx", "trend_ema_fast", "trend_ema_slow", 
                "trend_fast_rising_3", "atr_pct", "di_diff", "macd_hist_slope", "rsi_mom"]
    if not all(col in df.columns for col in required):
        return "HOLD"
    
    macd = latest["macd"]
    macd_signal = latest["macd_signal"]
    prev_macd = prev["macd"]
    prev_macd_signal = prev["macd_signal"]
    rsi = latest["rsi"]
    adx = latest["adx"]
    trend_ema_fast = latest["trend_ema_fast"]
    trend_ema_slow = latest["trend_ema_slow"]
    trend_fast_rising_3 = latest["trend_fast_rising_3"]
    
    # Module 4 indicators
    atr_pct = latest["atr_pct"]
    di_diff = latest["di_diff"]
    macd_hist_slope = latest["macd_hist_slope"]
    rsi_mom = latest["rsi_mom"]
    
    # Check for NaN
    if pd.isna(macd) or pd.isna(macd_signal) or pd.isna(rsi) or pd.isna(adx) or pd.isna(trend_ema_fast) or pd.isna(trend_ema_slow) or pd.isna(trend_fast_rising_3):
        return "HOLD"
    if pd.isna(atr_pct) or pd.isna(di_diff) or pd.isna(macd_hist_slope) or pd.isna(rsi_mom):
        return "HOLD"
    
    # ========== ENTRY LOGIC (MODULE 4 ENHANCED) ==========
    
    # 1) Soft trend confirmation (PRESERVED from previous implementation)
    trend_ok = (
        (trend_ema_fast > trend_ema_slow) or trend_fast_rising_3
    )
    
    # 2) ATR volatility filter - only enter when market is moving
    atr_ok = atr_pct >= atr_vol_thresh
    
    # 3) ADX trend strength filter (existing)
    adx_ok = adx >= adx_min
    
    # 4) Directional movement filter - DI+ must dominate DI-
    di_ok = di_diff >= di_margin
    
    # 5) MACD crossover (existing)
    macd_up = (prev_macd <= prev_macd_signal) and (macd > macd_signal)
    
    # 6) MACD histogram momentum - histogram must be accelerating upward
    macd_mom_ok = macd_hist_slope > 0
    
    # 7) RSI momentum - RSI must be rising from oversold zone (35-55 band)
    rsi_ok = (rsi_mom > 0) and (rsi >= rsi_buy) and (rsi <= 55.0)
    
    # BUY signal: ALL conditions must be met
    if trend_ok and atr_ok and adx_ok and di_ok and macd_up and macd_mom_ok and rsi_ok:
        return "BUY"
    
    # ========== EXIT LOGIC (UNCHANGED) ==========
    
    # Exit signal: RSI above exit threshold
    if rsi > rsi_exit:
        return "SELL"
    
    return "HOLD"
