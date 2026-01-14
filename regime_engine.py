"""
MODULE 12: Market Regime Detection Engine

Classifies current market conditions into TRENDING, RANGING, BREAKOUT, or NEUTRAL.
Used to dynamically adjust strategy parameters based on market regime.
"""

import pandas as pd
import numpy as np
from typing import Optional


# Regime classification thresholds (module-level constants for easy tuning)

# TRENDING regime thresholds
TRENDING_ADX_MIN = 22.0
TRENDING_EMA_SPREAD_PCT = 0.0015  # 0.15% minimum EMA separation
TRENDING_CONSISTENCY_BARS = 3     # Number of bars to check price/EMA alignment

# RANGING regime thresholds
RANGING_ADX_MAX = 18.0
RANGING_EMA_SPREAD_PCT = 0.0015   # 0.15% maximum EMA separation
RANGING_ATR_SLOPE_THRESHOLD = -0.05  # ATR should be flat or decreasing

# BREAKOUT regime thresholds
BREAKOUT_ATR_INCREASE_PCT = 0.15  # 15% ATR increase over lookback
BREAKOUT_ATR_LOOKBACK = 10        # Bars to compare ATR
BREAKOUT_CANDLE_ATR_MULT = 1.5    # Candle size relative to ATR
BREAKOUT_PRICE_ATR_MULT = 1.0     # Price distance from EMA in ATR units


def detect_regime(df: pd.DataFrame, bar_index: int = -1) -> str:
    """
    Detect market regime based on indicators.
    
    Args:
        df: DataFrame with OHLCV and indicators (close, ema_fast, ema_slow, adx, atr)
        bar_index: Index of the bar to analyze (default: -1 for most recent)
    
    Returns:
        str: One of "TRENDING", "RANGING", "BREAKOUT", "NEUTRAL"
    """
    # Handle empty or insufficient data
    if df is None or len(df) < 20:
        return "NEUTRAL"
    
    # Get the current bar
    if bar_index == -1:
        bar_index = len(df) - 1
    
    if bar_index < 10:  # Need history for slope calculations
        return "NEUTRAL"
    
    try:
        row = df.iloc[bar_index]
        
        # Extract required values
        close = float(row.get("close", 0))
        ema_fast = float(row.get("ema_fast", 0))
        ema_slow = float(row.get("ema_slow", 0))
        adx = float(row.get("adx", 0))
        atr = float(row.get("atr", 0))
        high = float(row.get("high", 0))
        low = float(row.get("low", 0))
        
        # Validate data
        if close <= 0 or atr <= 0 or ema_fast <= 0 or ema_slow <= 0:
            return "NEUTRAL"
        
        # Calculate EMA spread as percentage of price
        ema_spread_pct = abs(ema_fast - ema_slow) / close
        
        # Check for BREAKOUT first (highest priority)
        if _is_breakout_regime(df, bar_index, close, ema_fast, atr, high, low):
            return "BREAKOUT"
        
        # Check for TRENDING
        if _is_trending_regime(df, bar_index, adx, ema_spread_pct, close, ema_fast, ema_slow):
            return "TRENDING"
        
        # Check for RANGING
        if _is_ranging_regime(df, bar_index, adx, ema_spread_pct, atr):
            return "RANGING"
        
        # Default to NEUTRAL
        return "NEUTRAL"
        
    except Exception as e:
        # Fail gracefully
        return "NEUTRAL"


def _is_trending_regime(df: pd.DataFrame, bar_index: int, adx: float, 
                        ema_spread_pct: float, close: float, 
                        ema_fast: float, ema_slow: float) -> bool:
    """Check if market is in TRENDING regime."""
    
    # ADX must be strong
    if adx < TRENDING_ADX_MIN:
        return False
    
    # EMAs must be separated
    if ema_spread_pct < TRENDING_EMA_SPREAD_PCT:
        return False
    
    # Check price consistency with EMAs over recent bars
    start_idx = max(0, bar_index - TRENDING_CONSISTENCY_BARS + 1)
    recent_bars = df.iloc[start_idx:bar_index + 1]
    
    if len(recent_bars) < 2:
        return False
    
    # Count bars where price aligns with EMA trend
    aligned_bars = 0
    is_uptrend = ema_fast > ema_slow
    
    for idx in range(len(recent_bars)):
        bar_close = float(recent_bars.iloc[idx].get("close", 0))
        bar_ema_fast = float(recent_bars.iloc[idx].get("ema_fast", 0))
        bar_ema_slow = float(recent_bars.iloc[idx].get("ema_slow", 0))
        
        if bar_close <= 0 or bar_ema_fast <= 0 or bar_ema_slow <= 0:
            continue
        
        if is_uptrend:
            # For uptrend: price should be above both EMAs
            if bar_close > bar_ema_fast and bar_close > bar_ema_slow:
                aligned_bars += 1
        else:
            # For downtrend: price should be below both EMAs
            if bar_close < bar_ema_fast and bar_close < bar_ema_slow:
                aligned_bars += 1
    
    # Require majority of recent bars to be aligned
    return aligned_bars >= (TRENDING_CONSISTENCY_BARS * 0.6)


def _is_ranging_regime(df: pd.DataFrame, bar_index: int, adx: float, 
                       ema_spread_pct: float, atr: float) -> bool:
    """Check if market is in RANGING regime."""
    
    # ADX must be weak
    if adx >= RANGING_ADX_MAX:
        return False
    
    # EMAs must be close together
    if ema_spread_pct >= RANGING_EMA_SPREAD_PCT:
        return False
    
    # ATR should be flat or decreasing (compare recent vs older ATR)
    lookback = 5
    if bar_index < lookback * 2:
        return True  # Can't check slope, but other conditions met
    
    try:
        recent_atr = df.iloc[bar_index - lookback + 1:bar_index + 1]["atr"].mean()
        older_atr = df.iloc[bar_index - lookback * 2 + 1:bar_index - lookback + 1]["atr"].mean()
        
        if pd.isna(recent_atr) or pd.isna(older_atr) or older_atr <= 0:
            return True  # Can't check slope reliably
        
        atr_slope = (recent_atr - older_atr) / older_atr
        
        return atr_slope <= RANGING_ATR_SLOPE_THRESHOLD
        
    except Exception:
        return True  # If slope calc fails, accept other ranging conditions


def _is_breakout_regime(df: pd.DataFrame, bar_index: int, close: float,
                        ema_fast: float, atr: float, high: float, low: float) -> bool:
    """Check if market is in BREAKOUT (high volatility) regime."""
    
    # Check ATR increase over lookback period
    if bar_index >= BREAKOUT_ATR_LOOKBACK:
        try:
            old_atr = float(df.iloc[bar_index - BREAKOUT_ATR_LOOKBACK].get("atr", 0))
            
            if old_atr > 0:
                atr_increase = (atr - old_atr) / old_atr
                
                # Strong ATR increase indicates breakout
                if atr_increase > BREAKOUT_ATR_INCREASE_PCT:
                    return True
        except Exception:
            pass
    
    # Check for large candle relative to ATR
    if atr > 0:
        candle_size = high - low
        
        if candle_size > BREAKOUT_CANDLE_ATR_MULT * atr:
            # Additional check: price deviation from EMA
            price_deviation = abs(close - ema_fast)
            
            if price_deviation > BREAKOUT_PRICE_ATR_MULT * atr:
                return True
    
    return False


def classify_regime(df: pd.DataFrame, lookback: int = 20) -> str:
    """
    Convenience wrapper to classify the current market regime.
    
    Args:
        df: DataFrame with OHLCV and indicators
        lookback: Number of recent bars to consider (for context)
    
    Returns:
        str: Current regime classification
    """
    if df is None or len(df) < lookback:
        return "NEUTRAL"
    
    # Use the most recent bar for classification
    return detect_regime(df, bar_index=-1)


def get_regime_summary(df: pd.DataFrame, start_index: int = 0) -> dict:
    """
    Analyze regime distribution over a DataFrame.
    
    Args:
        df: DataFrame with OHLCV and indicators
        start_index: Starting index for analysis
    
    Returns:
        dict: Regime counts and percentages
    """
    if df is None or len(df) <= start_index:
        return {}
    
    regimes = []
    for i in range(max(start_index, 20), len(df)):
        regime = detect_regime(df, i)
        regimes.append(regime)
    
    if not regimes:
        return {}
    
    from collections import Counter
    regime_counts = Counter(regimes)
    total = len(regimes)
    
    summary = {}
    for regime, count in regime_counts.items():
        summary[regime] = {
            "count": count,
            "percentage": (count / total * 100) if total > 0 else 0.0
        }
    
    return summary
