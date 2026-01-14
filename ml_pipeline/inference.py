"""
MODULE 17: Inference Utilities

Shared utilities for ML model inference during trading.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def predict_signal(
    model: Any,
    features: np.ndarray,
    min_confidence: float = 0.55
) -> Dict[str, Any]:
    """
    Generate trading signal from model predictions.
    
    Args:
        model: Trained ML model
        features: Feature array for prediction
        min_confidence: Minimum confidence threshold for signals
        
    Returns:
        Dict with signal, confidence, and metadata
    """
    # Reshape features if needed
    if len(features.shape) == 1:
        features = features.reshape(1, -1)
    
    # Get prediction
    try:
        # Try to get probability predictions
        if hasattr(model, 'predict_proba'):
            probabilities = model.predict_proba(features)[0]
            prediction = np.argmax(probabilities)
            confidence = probabilities[prediction]
        else:
            # Fallback to hard predictions
            prediction = model.predict(features)[0]
            confidence = 1.0  # No confidence info available
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return {
            'signal': 'FLAT',
            'confidence': 0.0,
            'raw_prediction': None,
            'error': str(e)
        }
    
    # Map prediction to signal
    # sklearn classifiers with predict_proba use class indices (0, 1, 2)
    # Our labels are: -1=SHORT, 0=FLAT, 1=LONG
    # So class 0 = -1 (SHORT), class 1 = 0 (FLAT), class 2 = 1 (LONG)
    if hasattr(model, 'predict_proba'):
        # Using class indices
        signal_map = {
            0: 'SHORT',  # class index 0 maps to label -1
            1: 'FLAT',   # class index 1 maps to label 0
            2: 'LONG'    # class index 2 maps to label 1
        }
    else:
        # Direct label mapping
        signal_map = {
            -1: 'SHORT',
            0: 'FLAT',
            1: 'LONG'
        }
    
    signal = signal_map.get(prediction, 'FLAT')
    
    # Apply confidence threshold
    if confidence < min_confidence:
        signal = 'FLAT'
        logger.debug(f"Low confidence ({confidence:.3f}), defaulting to FLAT")
    
    result = {
        'signal': signal,
        'confidence': float(confidence),
        'raw_prediction': int(prediction),
        'probabilities': probabilities.tolist() if hasattr(model, 'predict_proba') else None
    }
    
    logger.debug(f"Prediction: {signal} (confidence: {confidence:.3f})")
    
    return result


def predict_with_features(
    model: Any,
    df: pd.DataFrame,
    feature_cols: list,
    min_confidence: float = 0.55
) -> Dict[str, Any]:
    """
    Predict signal from DataFrame with features.
    
    Args:
        model: Trained ML model
        df: DataFrame with computed features
        feature_cols: List of feature column names
        min_confidence: Minimum confidence threshold
        
    Returns:
        Dict with signal and metadata
    """
    # Extract features from last row
    try:
        features = df[feature_cols].iloc[-1].values
    except Exception as e:
        logger.error(f"Error extracting features: {e}")
        return {
            'signal': 'FLAT',
            'confidence': 0.0,
            'error': str(e)
        }
    
    # Check for NaN values
    if np.isnan(features).any():
        logger.warning("NaN values in features, returning FLAT")
        return {
            'signal': 'FLAT',
            'confidence': 0.0,
            'error': 'NaN values in features'
        }
    
    # Predict
    return predict_signal(model, features, min_confidence)


def calculate_signal_strength(
    prediction_result: Dict[str, Any],
    atr: Optional[float] = None,
    volatility: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculate signal strength and recommended stop-loss/take-profit.
    
    Args:
        prediction_result: Result from predict_signal
        atr: Current ATR value (optional)
        volatility: Current volatility estimate (optional)
        
    Returns:
        Dict with signal strength and recommended risk parameters
    """
    signal = prediction_result['signal']
    confidence = prediction_result['confidence']
    
    # Base signal strength on confidence
    strength = confidence
    
    # Adjust for volatility if available
    if volatility is not None:
        # Higher volatility = wider stops
        vol_multiplier = min(2.0, 1.0 + volatility)
    else:
        vol_multiplier = 1.0
    
    # Calculate recommended SL/TP distances
    if atr is not None and atr > 0:
        # ATR-based stops
        base_sl_atr = 1.5
        base_tp_atr = 3.0
        
        # Adjust based on confidence
        # Higher confidence = tighter stops (more aggressive)
        confidence_adj = 1.0 - (confidence - 0.5) * 0.5  # Range: 0.75 to 1.0
        
        sl_distance = atr * base_sl_atr * vol_multiplier * confidence_adj
        tp_distance = atr * base_tp_atr * vol_multiplier * confidence_adj
    else:
        # Default percentage-based if no ATR
        sl_distance = None
        tp_distance = None
    
    result = {
        'signal': signal,
        'strength': strength,
        'confidence': confidence,
        'sl_distance': sl_distance,
        'tp_distance': tp_distance,
        'volatility_multiplier': vol_multiplier
    }
    
    return result
