"""
MODULE 17: Feature Engineering

Advanced feature engineering for ML-based trading strategies.
Includes technical indicators, normalized features, and rolling windows.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr


def add_price_features(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Add normalized OHLC features.
    
    Args:
        df: OHLCV DataFrame
        config: Optional configuration dict
        
    Returns:
        DataFrame with added price features
    """
    df = df.copy()
    
    # Normalized OHLC changes (relative to close)
    df['norm_open'] = (df['open'] - df['close']) / df['close']
    df['norm_high'] = (df['high'] - df['close']) / df['close']
    df['norm_low'] = (df['low'] - df['close']) / df['close']
    
    # High-Low range
    df['hl_range'] = (df['high'] - df['low']) / df['close']
    
    # Close-Open change
    df['co_change'] = (df['close'] - df['open']) / df['open']
    
    # Body ratio (candle body vs total range)
    total_range = df['high'] - df['low']
    body = abs(df['close'] - df['open'])
    df['body_ratio'] = np.where(total_range > 0, body / total_range, 0)
    
    # Upper/lower shadows
    df['upper_shadow'] = np.where(
        df['close'] > df['open'],
        (df['high'] - df['close']) / df['close'],
        (df['high'] - df['open']) / df['close']
    )
    df['lower_shadow'] = np.where(
        df['close'] > df['open'],
        (df['open'] - df['low']) / df['close'],
        (df['close'] - df['low']) / df['close']
    )
    
    return df


def add_return_features(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Add return-based features.
    
    Args:
        df: OHLCV DataFrame
        config: Optional configuration dict
        
    Returns:
        DataFrame with return features
    """
    df = df.copy()
    
    # Simple returns
    df['return_1'] = df['close'].pct_change(1)
    df['return_5'] = df['close'].pct_change(5)
    df['return_10'] = df['close'].pct_change(10)
    
    # Log returns
    df['log_return_1'] = np.log(df['close'] / df['close'].shift(1))
    df['log_return_5'] = np.log(df['close'] / df['close'].shift(5))
    
    # Return volatility (rolling std)
    df['return_volatility_5'] = df['return_1'].rolling(window=5).std()
    df['return_volatility_20'] = df['return_1'].rolling(window=20).std()
    
    return df


def add_ema_features(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Add EMA-based features.
    
    Args:
        df: OHLCV DataFrame
        config: Optional configuration dict
        
    Returns:
        DataFrame with EMA features
    """
    df = df.copy()
    
    # Default EMA periods
    periods = config.get('ema_periods', [5, 9, 20, 50]) if config else [5, 9, 20, 50]
    
    for period in periods:
        df[f'ema_{period}'] = calculate_ema(df['close'], period)
        # Normalized distance from EMA
        df[f'ema_{period}_dist'] = (df['close'] - df[f'ema_{period}']) / df['close']
    
    # EMA crossovers (fast vs slow)
    if 5 in periods and 9 in periods:
        df['ema_cross_5_9'] = df['ema_5'] - df['ema_9']
    if 9 in periods and 20 in periods:
        df['ema_cross_9_20'] = df['ema_9'] - df['ema_20']
    if 20 in periods and 50 in periods:
        df['ema_cross_20_50'] = df['ema_20'] - df['ema_50']
    
    return df


def add_rsi_features(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Add RSI-based features.
    
    Args:
        df: OHLCV DataFrame
        config: Optional configuration dict
        
    Returns:
        DataFrame with RSI features
    """
    df = df.copy()
    
    # Default RSI periods
    periods = config.get('rsi_periods', [7, 14]) if config else [7, 14]
    
    for period in periods:
        df[f'rsi_{period}'] = calculate_rsi(df['close'], period)
        
        # Normalized RSI (0-1 range)
        df[f'rsi_{period}_norm'] = df[f'rsi_{period}'] / 100.0
        
        # RSI zones
        df[f'rsi_{period}_oversold'] = (df[f'rsi_{period}'] < 30).astype(int)
        df[f'rsi_{period}_overbought'] = (df[f'rsi_{period}'] > 70).astype(int)
    
    return df


def add_volume_features(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Add volume-based features.
    
    Args:
        df: OHLCV DataFrame
        config: Optional configuration dict
        
    Returns:
        DataFrame with volume features
    """
    df = df.copy()
    
    # Volume moving averages
    df['volume_ma_5'] = df['volume'].rolling(window=5).mean()
    df['volume_ma_20'] = df['volume'].rolling(window=20).mean()
    
    # Volume ratio (current vs average)
    df['volume_ratio_5'] = df['volume'] / df['volume_ma_5']
    df['volume_ratio_20'] = df['volume'] / df['volume_ma_20']
    
    # Volume z-score
    df['volume_zscore'] = (
        (df['volume'] - df['volume'].rolling(window=20).mean()) /
        df['volume'].rolling(window=20).std()
    )
    
    # Volume trend
    df['volume_change'] = df['volume'].pct_change()
    
    # Price-volume correlation
    df['pv_corr_10'] = df['close'].rolling(window=10).corr(df['volume'])
    
    return df


def add_volatility_features(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Add volatility-based features (ATR, etc.).
    
    Args:
        df: OHLCV DataFrame
        config: Optional configuration dict
        
    Returns:
        DataFrame with volatility features
    """
    df = df.copy()
    
    # ATR
    df['atr_14'] = calculate_atr(df, period=14)
    df['atr_7'] = calculate_atr(df, period=7)
    
    # Normalized ATR (as % of price)
    df['atr_14_pct'] = df['atr_14'] / df['close']
    df['atr_7_pct'] = df['atr_7'] / df['close']
    
    # Historical volatility (rolling std of returns)
    df['hist_vol_10'] = df['close'].pct_change().rolling(window=10).std()
    df['hist_vol_20'] = df['close'].pct_change().rolling(window=20).std()
    
    # Parkinson volatility (high-low estimator)
    df['parkinson_vol'] = np.sqrt(
        (1 / (4 * np.log(2))) *
        (np.log(df['high'] / df['low']) ** 2).rolling(window=10).mean()
    )
    
    return df


def add_momentum_features(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Add momentum-based features.
    
    Args:
        df: OHLCV DataFrame
        config: Optional configuration dict
        
    Returns:
        DataFrame with momentum features
    """
    df = df.copy()
    
    # Rate of Change (ROC)
    df['roc_5'] = ((df['close'] - df['close'].shift(5)) / df['close'].shift(5)) * 100
    df['roc_10'] = ((df['close'] - df['close'].shift(10)) / df['close'].shift(10)) * 100
    
    # Momentum
    df['momentum_5'] = df['close'] - df['close'].shift(5)
    df['momentum_10'] = df['close'] - df['close'].shift(10)
    
    # Acceleration (momentum of momentum)
    df['acceleration_5'] = df['momentum_5'].diff()
    
    return df


def build_feature_matrix(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
    feature_window: Optional[int] = None
) -> pd.DataFrame:
    """
    Build complete feature matrix for ML training or inference.
    
    This is the main entry point for feature engineering.
    
    Args:
        df: OHLCV DataFrame
        config: Optional configuration dict with feature settings
        feature_window: Optional rolling window size for sequences
        
    Returns:
        DataFrame with all engineered features
    """
    logger.info("Building feature matrix...")
    
    if config is None:
        config = {}
    
    # Add all feature groups
    df = add_price_features(df, config)
    df = add_return_features(df, config)
    df = add_ema_features(df, config)
    df = add_rsi_features(df, config)
    df = add_volume_features(df, config)
    df = add_volatility_features(df, config)
    df = add_momentum_features(df, config)
    
    # Remove rows with NaN values (from rolling calculations)
    initial_len = len(df)
    df = df.dropna()
    
    if len(df) < initial_len:
        logger.info(f"Removed {initial_len - len(df)} rows with NaN values after feature engineering")
    
    logger.info(f"Feature matrix created: {len(df)} rows, {len(df.columns)} columns")
    
    return df


def get_feature_columns(df: pd.DataFrame) -> List[str]:
    """
    Get list of feature columns (exclude OHLCV, timestamp, label).
    
    Args:
        df: DataFrame with features
        
    Returns:
        List of feature column names
    """
    exclude_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                    'label', 'future_close', 'future_return']
    
    # Also exclude any EMA columns (raw values, we keep distance features)
    exclude_patterns = ['ema_5', 'ema_9', 'ema_20', 'ema_50', 'ema_100', 'ema_200']
    
    feature_cols = [
        col for col in df.columns 
        if col not in exclude_cols 
        and not any(col == pattern for pattern in exclude_patterns)
    ]
    
    return feature_cols


def create_rolling_windows(
    df: pd.DataFrame,
    feature_cols: List[str],
    window_size: int
) -> np.ndarray:
    """
    Create rolling window sequences for time-series models (LSTM, etc.).
    
    Args:
        df: DataFrame with features
        feature_cols: List of feature column names
        window_size: Size of rolling window
        
    Returns:
        3D numpy array: (samples, window_size, features)
    """
    features = df[feature_cols].values
    n_samples = len(features) - window_size + 1
    n_features = len(feature_cols)
    
    windows = np.zeros((n_samples, window_size, n_features))
    
    for i in range(n_samples):
        windows[i] = features[i:i+window_size]
    
    logger.info(f"Created rolling windows: shape {windows.shape}")
    
    return windows
