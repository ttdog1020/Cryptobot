"""
MODULE 17: Data Preprocessing

Load, clean, and align OHLCV data for ML training and inference.
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def load_ohlcv_data(filepath: str) -> pd.DataFrame:
    """
    Load OHLCV data from CSV file.
    
    Args:
        filepath: Path to CSV file with OHLCV data
        
    Returns:
        DataFrame with standardized columns
    """
    df = pd.read_csv(filepath)
    
    # Standardize column names
    column_mapping = {
        'timestamp': 'timestamp',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume'
    }
    
    # Rename if needed (case-insensitive)
    df.columns = df.columns.str.lower()
    
    # Ensure required columns exist
    required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    # Convert timestamp to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Sort by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    logger.info(f"Loaded {len(df)} rows from {filepath}")
    return df


def clean_ohlcv_data(df: pd.DataFrame, remove_outliers: bool = True) -> pd.DataFrame:
    """
    Clean OHLCV data by handling missing values and outliers.
    
    Args:
        df: Raw OHLCV DataFrame
        remove_outliers: Whether to remove extreme outliers
        
    Returns:
        Cleaned DataFrame
    """
    df = df.copy()
    
    # Remove rows with missing OHLCV values
    initial_len = len(df)
    df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
    
    if len(df) < initial_len:
        logger.warning(f"Removed {initial_len - len(df)} rows with missing values")
    
    # Ensure OHLC consistency (high >= low, etc.)
    invalid_mask = (df['high'] < df['low']) | (df['high'] < df['close']) | (df['high'] < df['open'])
    if invalid_mask.any():
        logger.warning(f"Found {invalid_mask.sum()} rows with invalid OHLC relationships, removing")
        df = df[~invalid_mask]
    
    # Remove zero or negative prices
    price_cols = ['open', 'high', 'low', 'close']
    zero_mask = (df[price_cols] <= 0).any(axis=1)
    if zero_mask.any():
        logger.warning(f"Removed {zero_mask.sum()} rows with zero/negative prices")
        df = df[~zero_mask]
    
    # Remove extreme outliers (optional)
    if remove_outliers:
        for col in price_cols:
            q1 = df[col].quantile(0.01)
            q99 = df[col].quantile(0.99)
            iqr = q99 - q1
            lower_bound = q1 - 3 * iqr
            upper_bound = q99 + 3 * iqr
            
            outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
            if outlier_mask.any():
                logger.warning(f"Removed {outlier_mask.sum()} outliers from {col}")
                df = df[~outlier_mask]
    
    # Reset index
    df = df.reset_index(drop=True)
    
    logger.info(f"Cleaned data: {len(df)} rows remaining")
    return df


def align_data_for_training(
    df: pd.DataFrame,
    prediction_horizon: int = 1
) -> pd.DataFrame:
    """
    Align data for supervised learning by creating labels.
    
    Args:
        df: OHLCV DataFrame
        prediction_horizon: Number of periods ahead to predict
        
    Returns:
        DataFrame with 'label' column (1=LONG, -1=SHORT, 0=FLAT)
    """
    df = df.copy()
    
    # Calculate future returns
    df['future_close'] = df['close'].shift(-prediction_horizon)
    df['future_return'] = (df['future_close'] - df['close']) / df['close']
    
    # Create labels based on future returns
    # LONG if future return > threshold
    # SHORT if future return < -threshold
    # FLAT otherwise
    threshold = 0.001  # 0.1% threshold for signal generation
    
    df['label'] = 0  # Default to FLAT
    df.loc[df['future_return'] > threshold, 'label'] = 1   # LONG
    df.loc[df['future_return'] < -threshold, 'label'] = -1  # SHORT
    
    # Remove rows without future data
    df = df.dropna(subset=['future_close', 'future_return'])
    
    logger.info(f"Label distribution: "
                f"LONG={len(df[df['label']==1])}, "
                f"SHORT={len(df[df['label']==-1])}, "
                f"FLAT={len(df[df['label']==0])}")
    
    return df


def split_train_test(
    df: pd.DataFrame,
    train_ratio: float = 0.8
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split data into train and test sets chronologically.
    
    Args:
        df: DataFrame with features and labels
        train_ratio: Proportion of data for training
        
    Returns:
        Tuple of (train_df, test_df)
    """
    split_idx = int(len(df) * train_ratio)
    
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    
    logger.info(f"Train size: {len(train_df)}, Test size: {len(test_df)}")
    
    return train_df, test_df


def prepare_data_for_ml(
    filepath: str,
    prediction_horizon: int = 1,
    train_ratio: float = 0.8,
    remove_outliers: bool = True
) -> Dict[str, pd.DataFrame]:
    """
    Complete data preparation pipeline.
    
    Args:
        filepath: Path to OHLCV CSV file
        prediction_horizon: Periods ahead to predict
        train_ratio: Train/test split ratio
        remove_outliers: Whether to remove outliers
        
    Returns:
        Dict with 'train' and 'test' DataFrames
    """
    logger.info("Starting data preparation pipeline")
    
    # Load data
    df = load_ohlcv_data(filepath)
    
    # Clean data
    df = clean_ohlcv_data(df, remove_outliers=remove_outliers)
    
    # Create labels
    df = align_data_for_training(df, prediction_horizon=prediction_horizon)
    
    # Split data
    train_df, test_df = split_train_test(df, train_ratio=train_ratio)
    
    logger.info("Data preparation complete")
    
    return {
        'train': train_df,
        'test': test_df
    }
