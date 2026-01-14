"""
Synthetic Data Generation for Testing (Module 20)

Provides deterministic synthetic OHLCV data generators for testing
trading strategies, backtesting, and differential validation.

All functions use seeded random generation for reproducibility.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional


def generate_trend_series(
    symbol: str = "BTCUSDT",
    start_price: float = 50000.0,
    num_candles: int = 100,
    timeframe: str = "1h",
    trend_strength: float = 0.02,
    volatility: float = 0.005,
    seed: Optional[int] = 42
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data with a trending pattern.
    
    Args:
        symbol: Trading pair symbol
        start_price: Starting price
        num_candles: Number of candles to generate
        timeframe: Timeframe string (e.g., "1h", "15m")
        trend_strength: Strength of trend (0.02 = 2% per candle on average)
        volatility: Intra-candle volatility (0.005 = 0.5%)
        seed: Random seed for reproducibility
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume, symbol
    """
    if seed is not None:
        np.random.seed(seed)
    
    # Parse timeframe to timedelta
    timeframe_minutes = _parse_timeframe(timeframe)
    
    # Generate timestamps
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    timestamps = [start_time + timedelta(minutes=i * timeframe_minutes) 
                  for i in range(num_candles)]
    
    # Generate trending prices
    data = []
    current_price = start_price
    
    for i, ts in enumerate(timestamps):
        # Trend component
        trend_move = current_price * trend_strength * (0.5 + np.random.random())
        
        # Random walk component
        noise = current_price * volatility * np.random.randn()
        
        # Calculate close price
        close = current_price + trend_move + noise
        close = max(close, 0.01)  # Ensure positive
        
        # Generate OHLC based on close
        intra_volatility = close * volatility
        open_price = current_price
        high = max(open_price, close) + abs(np.random.normal(0, intra_volatility))
        low = min(open_price, close) - abs(np.random.normal(0, intra_volatility))
        low = max(low, close * 0.95)  # Prevent extreme wicks
        
        # Volume (slightly correlated with price movement)
        price_change_pct = abs((close - open_price) / open_price)
        base_volume = 100 + np.random.randint(0, 50)
        volume = base_volume * (1 + price_change_pct * 10)
        
        data.append({
            'timestamp': ts,
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': round(volume, 2),
            'symbol': symbol
        })
        
        current_price = close
    
    return pd.DataFrame(data)


def generate_range_series(
    symbol: str = "ETHUSDT",
    center_price: float = 3000.0,
    num_candles: int = 100,
    timeframe: str = "1h",
    range_width: float = 0.03,
    volatility: float = 0.005,
    seed: Optional[int] = 42
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data with range-bound (sideways) pattern.
    
    Args:
        symbol: Trading pair symbol
        center_price: Center price of the range
        num_candles: Number of candles to generate
        timeframe: Timeframe string
        range_width: Width of range as fraction (0.03 = 3% on each side)
        volatility: Intra-candle volatility
        seed: Random seed for reproducibility
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume, symbol
    """
    if seed is not None:
        np.random.seed(seed)
    
    timeframe_minutes = _parse_timeframe(timeframe)
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    timestamps = [start_time + timedelta(minutes=i * timeframe_minutes) 
                  for i in range(num_candles)]
    
    # Range bounds
    upper_bound = center_price * (1 + range_width)
    lower_bound = center_price * (1 - range_width)
    
    data = []
    current_price = center_price
    
    for i, ts in enumerate(timestamps):
        # Mean reversion force (push back toward center)
        distance_from_center = current_price - center_price
        reversion_force = -distance_from_center * 0.1
        
        # Random oscillation
        oscillation = center_price * range_width * np.random.randn() * 0.3
        
        # Calculate close price
        close = current_price + reversion_force + oscillation
        close = np.clip(close, lower_bound, upper_bound)
        
        # Generate OHLC
        intra_volatility = close * volatility
        open_price = current_price
        high = max(open_price, close) + abs(np.random.normal(0, intra_volatility))
        low = min(open_price, close) - abs(np.random.normal(0, intra_volatility))
        
        # Clip to range bounds
        high = min(high, upper_bound)
        low = max(low, lower_bound)
        
        # Volume
        base_volume = 80 + np.random.randint(0, 40)
        volume = base_volume * np.random.uniform(0.8, 1.2)
        
        data.append({
            'timestamp': ts,
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': round(volume, 2),
            'symbol': symbol
        })
        
        current_price = close
    
    return pd.DataFrame(data)


def generate_spike_series(
    symbol: str = "SOLUSDT",
    base_price: float = 100.0,
    num_candles: int = 100,
    timeframe: str = "15m",
    spike_candle: int = 50,
    spike_magnitude: float = 0.10,
    volatility: float = 0.003,
    seed: Optional[int] = 42
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data with a sharp price spike at specified candle.
    
    Useful for testing stop-loss, liquidation, and extreme volatility scenarios.
    
    Args:
        symbol: Trading pair symbol
        base_price: Base price level
        num_candles: Number of candles to generate
        timeframe: Timeframe string
        spike_candle: Index of candle where spike occurs
        spike_magnitude: Magnitude of spike as fraction (0.10 = 10% move)
        volatility: Normal volatility outside spike
        seed: Random seed for reproducibility
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume, symbol
    """
    if seed is not None:
        np.random.seed(seed)
    
    timeframe_minutes = _parse_timeframe(timeframe)
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    timestamps = [start_time + timedelta(minutes=i * timeframe_minutes) 
                  for i in range(num_candles)]
    
    data = []
    current_price = base_price
    
    for i, ts in enumerate(timestamps):
        open_price = current_price
        
        # Check if this is the spike candle
        if i == spike_candle:
            # Sharp upward spike
            spike_move = base_price * spike_magnitude
            close = current_price + spike_move
            high = close * 1.02  # Overshoot slightly
            low = open_price * 0.99  # Minor wick down
            
            # High volume on spike
            volume = 500 + np.random.randint(0, 200)
        
        elif i == spike_candle + 1:
            # Reversion after spike
            reversion = -spike_magnitude * 0.7
            close = current_price + (base_price * reversion)
            high = current_price
            low = close * 0.98
            
            volume = 300 + np.random.randint(0, 100)
        
        else:
            # Normal candle
            noise = current_price * volatility * np.random.randn()
            close = current_price + noise
            
            intra_volatility = close * volatility
            high = max(open_price, close) + abs(np.random.normal(0, intra_volatility))
            low = min(open_price, close) - abs(np.random.normal(0, intra_volatility))
            
            volume = 100 + np.random.randint(0, 50)
        
        # Ensure OHLC validity
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        low = max(low, 0.01)  # Ensure positive
        
        data.append({
            'timestamp': ts,
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': round(volume, 2),
            'symbol': symbol
        })
        
        current_price = close
    
    return pd.DataFrame(data)


def _parse_timeframe(timeframe: str) -> int:
    """
    Parse timeframe string to minutes.
    
    Args:
        timeframe: String like "1h", "15m", "1d"
    
    Returns:
        Number of minutes
    """
    timeframe = timeframe.lower()
    
    if timeframe.endswith('m'):
        return int(timeframe[:-1])
    elif timeframe.endswith('h'):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith('d'):
        return int(timeframe[:-1]) * 1440
    else:
        # Default to 1 hour
        return 60


def generate_multi_symbol_dataset(
    symbols: list = None,
    num_candles: int = 100,
    timeframe: str = "1h",
    seed: Optional[int] = 42
) -> pd.DataFrame:
    """
    Generate synchronized OHLCV data for multiple symbols.
    
    Args:
        symbols: List of symbol strings (default: ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        num_candles: Number of candles per symbol
        timeframe: Timeframe string
        seed: Random seed for reproducibility
    
    Returns:
        Combined DataFrame with all symbols
    """
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    
    all_data = []
    
    for i, symbol in enumerate(symbols):
        # Use different seed for each symbol
        symbol_seed = seed + i if seed is not None else None
        
        # Vary the pattern by symbol
        if i % 3 == 0:
            df = generate_trend_series(
                symbol=symbol,
                num_candles=num_candles,
                timeframe=timeframe,
                seed=symbol_seed
            )
        elif i % 3 == 1:
            df = generate_range_series(
                symbol=symbol,
                num_candles=num_candles,
                timeframe=timeframe,
                seed=symbol_seed
            )
        else:
            df = generate_spike_series(
                symbol=symbol,
                num_candles=num_candles,
                timeframe=timeframe,
                seed=symbol_seed
            )
        
        all_data.append(df)
    
    return pd.concat(all_data, ignore_index=True)
