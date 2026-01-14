"""
MODULE 15: Scalping Strategy - EMA + RSI

High-frequency scalping strategy optimized for 1m-5m timeframes.
Uses fast EMA crossovers, RSI momentum, and volume spikes.

Strategy Logic:
- LONG: EMA5 > EMA9, RSI(7) in [50, 75], volume spike
- SHORT: EMA5 < EMA9, RSI(7) in [25, 50], volume spike
- Filters: ATR minimum threshold, extreme RSI rejection

Integrates with RiskEngine for position sizing and SL/TP calculation.
"""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np


class ScalpingEMARSI:
    """
    Scalping strategy using EMA crossovers and RSI momentum.
    
    Attributes:
        ema_fast: Fast EMA period (default: 5)
        ema_slow: Slow EMA period (default: 9)
        rsi_period: RSI lookback period (default: 7)
        volume_multiplier: Volume spike threshold (default: 1.5x)
        atr_period: ATR calculation period (default: 14)
        atr_min_threshold: Minimum ATR to allow trades (default: 0.2)
        sl_atr_multiple: Stop-loss distance as ATR multiple (default: 0.25)
        tp_atr_multiple: Take-profit distance as ATR multiple (default: 0.5)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize scalping strategy with configuration.
        
        Args:
            config: Strategy parameters (optional, uses defaults if None)
        """
        config = config or {}
        
        # EMA parameters
        self.ema_fast = int(config.get("ema_fast", 5))
        self.ema_slow = int(config.get("ema_slow", 9))
        
        # RSI parameters
        self.rsi_period = int(config.get("rsi_period", 7))
        self.rsi_long_min = float(config.get("rsi_long_min", 50))
        self.rsi_long_max = float(config.get("rsi_long_max", 75))
        self.rsi_short_min = float(config.get("rsi_short_min", 25))
        self.rsi_short_max = float(config.get("rsi_short_max", 50))
        self.rsi_extreme_low = float(config.get("rsi_extreme_low", 20))
        self.rsi_extreme_high = float(config.get("rsi_extreme_high", 80))
        
        # Volume parameters
        self.volume_multiplier = float(config.get("volume_multiplier", 1.5))
        self.volume_lookback = int(config.get("volume_lookback", 20))
        
        # ATR parameters
        self.atr_period = int(config.get("atr_period", 14))
        self.atr_min_threshold = float(config.get("atr_min_threshold", 0.2))
        
        # Risk parameters (for metadata)
        self.sl_atr_multiple = float(config.get("sl_atr_multiple", 0.25))
        self.tp_atr_multiple = float(config.get("tp_atr_multiple", 0.5))
    
    @staticmethod
    def calculate_ema(series: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_rsi(series: pd.Series, period: int) -> pd.Series:
        """
        Calculate Relative Strength Index.
        
        Args:
            series: Price series (typically close prices)
            period: RSI lookback period
            
        Returns:
            RSI values (0-100)
        """
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int) -> pd.Series:
        """
        Calculate Average True Range.
        
        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            period: ATR lookback period
            
        Returns:
            ATR values
        """
        high = df["high"]
        low = df["low"]
        close = df["close"]
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add all required indicators to the dataframe.
        
        Args:
            df: OHLCV dataframe
            
        Returns:
            DataFrame with added indicator columns
        """
        df = df.copy()
        
        # EMAs
        df["ema_fast"] = self.calculate_ema(df["close"], self.ema_fast)
        df["ema_slow"] = self.calculate_ema(df["close"], self.ema_slow)
        
        # RSI
        df["rsi"] = self.calculate_rsi(df["close"], self.rsi_period)
        
        # ATR
        df["atr"] = self.calculate_atr(df, self.atr_period)
        
        # Volume average
        df["volume_avg"] = df["volume"].rolling(window=self.volume_lookback).mean()
        df["volume_spike"] = df["volume"] > (df["volume_avg"] * self.volume_multiplier)
        
        return df
    
    def detect_ema_cross(self, df: pd.DataFrame, index: int) -> Optional[str]:
        """
        Detect EMA crossover at given index.
        
        Args:
            df: DataFrame with ema_fast and ema_slow columns
            index: Current bar index
            
        Returns:
            "BULLISH" for upward cross, "BEARISH" for downward cross, None otherwise
        """
        if index < 1:
            return None
        
        curr_fast = df.iloc[index]["ema_fast"]
        curr_slow = df.iloc[index]["ema_slow"]
        prev_fast = df.iloc[index - 1]["ema_fast"]
        prev_slow = df.iloc[index - 1]["ema_slow"]
        
        # Bullish cross: fast was below, now above
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            return "BULLISH"
        
        # Bearish cross: fast was above, now below
        if prev_fast >= prev_slow and curr_fast < curr_slow:
            return "BEARISH"
        
        return None
    
    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate trading signal based on strategy rules.
        
        Args:
            df: DataFrame with OHLCV data and indicators
            
        Returns:
            Dictionary with:
                - signal: "LONG", "SHORT", or "FLAT"
                - metadata: Additional info (entry, sl_distance, tp_distance, etc.)
        """
        if len(df) < max(self.ema_slow, self.rsi_period, self.atr_period, self.volume_lookback):
            return {"signal": "FLAT", "metadata": {"reason": "insufficient_data"}}
        
        # Get last bar
        idx = len(df) - 1
        last = df.iloc[idx]
        
        # Extract values
        rsi = last["rsi"]
        atr = last["atr"]
        volume_spike = last["volume_spike"]
        close = last["close"]
        
        # Check if we have valid values
        if pd.isna(rsi) or pd.isna(atr) or pd.isna(volume_spike):
            return {"signal": "FLAT", "metadata": {"reason": "missing_indicators"}}
        
        # Filter 1: ATR minimum threshold
        if atr < self.atr_min_threshold:
            return {"signal": "FLAT", "metadata": {"reason": "low_volatility", "atr": atr}}
        
        # Filter 2: Extreme RSI (reject trades)
        if rsi < self.rsi_extreme_low or rsi > self.rsi_extreme_high:
            return {"signal": "FLAT", "metadata": {"reason": "extreme_rsi", "rsi": rsi}}
        
        # Filter 3: Volume spike required
        if not volume_spike:
            return {"signal": "FLAT", "metadata": {"reason": "no_volume_spike"}}
        
        # Detect EMA crossover
        cross = self.detect_ema_cross(df, idx)
        
        # LONG signal conditions
        if cross == "BULLISH":
            if self.rsi_long_min <= rsi <= self.rsi_long_max:
                metadata = {
                    "entry_price": close,
                    "sl_distance": atr * self.sl_atr_multiple,
                    "tp_distance": atr * self.tp_atr_multiple,
                    "atr": atr,
                    "rsi": rsi,
                    "cross": "BULLISH",
                    "volume_spike": True
                }
                return {"signal": "LONG", "metadata": metadata}
        
        # SHORT signal conditions
        if cross == "BEARISH":
            if self.rsi_short_min <= rsi <= self.rsi_short_max:
                metadata = {
                    "entry_price": close,
                    "sl_distance": atr * self.sl_atr_multiple,
                    "tp_distance": atr * self.tp_atr_multiple,
                    "atr": atr,
                    "rsi": rsi,
                    "cross": "BEARISH",
                    "volume_spike": True
                }
                return {"signal": "SHORT", "metadata": metadata}
        
        # No signal
        return {"signal": "FLAT", "metadata": {"reason": "no_setup", "rsi": rsi, "cross": cross}}


# Module-level convenience functions for backward compatibility
def add_indicators(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Add scalping indicators to dataframe.
    
    Args:
        df: OHLCV dataframe
        config: Strategy configuration (optional)
        
    Returns:
        DataFrame with indicators
    """
    strategy = ScalpingEMARSI(config)
    return strategy.add_indicators(df)


def generate_signal(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate trading signal for scalping strategy.
    
    Args:
        df: OHLCV dataframe with indicators
        config: Strategy configuration (optional)
        
    Returns:
        Signal string: "LONG", "SHORT", or "FLAT"
    """
    strategy = ScalpingEMARSI(config)
    result = strategy.generate_signal(df)
    return result["signal"]


def generate_signal_with_metadata(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generate trading signal with full metadata.
    
    Args:
        df: OHLCV dataframe with indicators
        config: Strategy configuration (optional)
        
    Returns:
        Dictionary with signal and metadata
    """
    strategy = ScalpingEMARSI(config)
    return strategy.generate_signal(df)
