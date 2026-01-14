"""
MODULE 17: ML Pipeline

Machine learning pipeline for data-driven trading strategies.
Includes feature engineering, model training, and inference.
"""

from .features import build_feature_matrix
from .model_registry import save_model, load_model, list_models
from .inference import predict_signal

__all__ = [
    'build_feature_matrix',
    'save_model',
    'load_model',
    'list_models',
    'predict_signal'
]
