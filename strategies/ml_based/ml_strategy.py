"""
MODULE 17: ML Strategy

Machine learning-based trading strategy wrapper.
Integrates with RiskEngine, backtesting, and live runtime.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from pathlib import Path
import logging

from ml_pipeline.model_registry import load_model, load_metadata
from ml_pipeline.features import build_feature_matrix, get_feature_columns
from ml_pipeline.inference import predict_with_features, calculate_signal_strength

logger = logging.getLogger(__name__)


class MLStrategy:
    """
    ML-based trading strategy.
    
    Loads a trained model and generates trading signals based on
    feature engineering and ML predictions.
    
    Compatible with:
    - RiskEngine (Module 14)
    - Backtesting system
    - Live async runtime (Module 16)
    """
    
    def __init__(
        self,
        model_name: str,
        min_confidence: float = 0.55,
        feature_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize ML strategy.
        
        Args:
            model_name: Name of trained model to load
            min_confidence: Minimum prediction confidence for signals
            feature_config: Optional feature engineering configuration
        """
        self.model_name = model_name
        self.min_confidence = min_confidence
        self.feature_config = feature_config or {}
        
        # Load model
        logger.info(f"Loading model: {model_name}")
        try:
            model_bundle = load_model(model_name)
            
            self.model = model_bundle['model']
            self.scaler = model_bundle['scaler']
            self.feature_cols = model_bundle['feature_cols']
            
            logger.info(f"Model loaded: {len(self.feature_cols)} features")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
        
        # Load metadata
        self.metadata = load_metadata(model_name)
        
        if self.metadata:
            logger.info(f"Model metadata: {self.metadata.get('model_type', 'unknown')} "
                       f"- Test accuracy: {self.metadata.get('metrics', {}).get('accuracy', 'N/A')}")
    
    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate trading signal from OHLCV data.
        
        This is the main entry point for signal generation.
        Compatible with backtesting and live runtime.
        
        Args:
            df: OHLCV DataFrame with sufficient history
            
        Returns:
            Dict with:
                - signal: 'LONG', 'SHORT', or 'FLAT'
                - metadata: Dict with entry_price, confidence, sl_distance, tp_distance
        """
        try:
            # Build features
            df_features = build_feature_matrix(df.copy(), self.feature_config)
            
            # Check if we have enough data
            if len(df_features) == 0:
                logger.warning("Insufficient data after feature engineering")
                return self._flat_signal("Insufficient data")
            
            # Ensure features match training
            missing_features = set(self.feature_cols) - set(df_features.columns)
            if missing_features:
                logger.error(f"Missing features: {missing_features}")
                return self._flat_signal(f"Missing features: {missing_features}")
            
            # Scale features
            X = df_features[self.feature_cols].iloc[-1:].values
            
            # Check for NaN
            if np.isnan(X).any():
                logger.warning("NaN values in features")
                return self._flat_signal("NaN in features")
            
            X_scaled = self.scaler.transform(X)
            
            # Predict
            if hasattr(self.model, 'predict_proba'):
                probabilities = self.model.predict_proba(X_scaled)[0]
                prediction = np.argmax(probabilities)
                confidence = probabilities[prediction]
            else:
                prediction = self.model.predict(X_scaled)[0]
                confidence = 1.0
            
            # Map prediction to signal
            signal_map = {1: 'LONG', -1: 'SHORT', 0: 'FLAT'}
            signal = signal_map.get(prediction, 'FLAT')
            
            # Apply confidence threshold
            if confidence < self.min_confidence:
                logger.debug(f"Low confidence ({confidence:.3f}), defaulting to FLAT")
                return self._flat_signal(f"Low confidence: {confidence:.3f}")
            
            # Get current price and ATR for metadata
            current_price = df['close'].iloc[-1]
            
            # Calculate ATR if available
            try:
                atr = df_features['atr_14'].iloc[-1] if 'atr_14' in df_features.columns else None
            except:
                atr = None
            
            # Calculate signal strength and risk parameters
            if atr and atr > 0:
                # ATR-based stops
                base_sl_mult = 1.5
                base_tp_mult = 3.0
                
                # Adjust based on confidence
                confidence_adj = 1.0 - (confidence - 0.5) * 0.3
                
                sl_distance = atr * base_sl_mult * confidence_adj
                tp_distance = atr * base_tp_mult * confidence_adj
            else:
                # Percentage-based fallback
                sl_distance = current_price * 0.02  # 2%
                tp_distance = current_price * 0.04  # 4%
            
            # Build metadata
            metadata = {
                'entry_price': current_price,
                'confidence': float(confidence),
                'raw_prediction': int(prediction),
                'sl_distance': float(sl_distance),
                'tp_distance': float(tp_distance),
                'atr': float(atr) if atr else None,
                'model_name': self.model_name,
                'strategy_type': 'ml_based'
            }
            
            if hasattr(self.model, 'predict_proba'):
                metadata['probabilities'] = probabilities.tolist()
            
            logger.info(f"ML Signal: {signal} (confidence: {confidence:.3f})")
            
            return {
                'signal': signal,
                'metadata': metadata
            }
        
        except Exception as e:
            logger.error(f"Error generating signal: {e}", exc_info=True)
            return self._flat_signal(f"Error: {str(e)}")
    
    def _flat_signal(self, reason: str) -> Dict[str, Any]:
        """
        Return a FLAT signal with reason.
        
        Args:
            reason: Reason for FLAT signal
            
        Returns:
            Signal dict with FLAT
        """
        return {
            'signal': 'FLAT',
            'metadata': {
                'reason': reason,
                'confidence': 0.0,
                'model_name': self.model_name,
                'strategy_type': 'ml_based'
            }
        }
    
    def get_required_history(self) -> int:
        """
        Get minimum required candles for signal generation.
        
        Returns:
            Minimum number of candles needed
        """
        # Need enough for longest indicator (e.g., EMA 50, RSI, etc.)
        return 100
    
    def __str__(self) -> str:
        """String representation."""
        return f"MLStrategy(model={self.model_name}, min_confidence={self.min_confidence})"
    
    def __repr__(self) -> str:
        """String representation."""
        return self.__str__()
