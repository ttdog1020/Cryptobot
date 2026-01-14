"""
MODULE 17: Model Training

Training entrypoint for ML trading models.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import logging

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler

from .data_prep import prepare_data_for_ml
from .features import build_feature_matrix, get_feature_columns
from .model_registry import save_model, load_model
from .inference import predict_signal

logger = logging.getLogger(__name__)


def load_training_data(
    filepath: str,
    prediction_horizon: int = 1,
    train_ratio: float = 0.8
) -> Dict[str, pd.DataFrame]:
    """
    Load and prepare training data.
    
    Args:
        filepath: Path to OHLCV CSV file
        prediction_horizon: Periods ahead to predict
        train_ratio: Train/test split ratio
        
    Returns:
        Dict with 'train' and 'test' DataFrames
    """
    logger.info(f"Loading training data from {filepath}")
    
    data = prepare_data_for_ml(
        filepath=filepath,
        prediction_horizon=prediction_horizon,
        train_ratio=train_ratio
    )
    
    return data


def build_features(
    data: Dict[str, pd.DataFrame],
    feature_config: Optional[Dict[str, Any]] = None
) -> Dict[str, pd.DataFrame]:
    """
    Build features for train and test sets.
    
    Args:
        data: Dict with 'train' and 'test' DataFrames
        feature_config: Optional feature configuration
        
    Returns:
        Dict with feature-enriched 'train' and 'test' DataFrames
    """
    logger.info("Building features...")
    
    train_df = build_feature_matrix(data['train'], feature_config)
    test_df = build_feature_matrix(data['test'], feature_config)
    
    return {
        'train': train_df,
        'test': test_df
    }


def train_model(
    train_df: pd.DataFrame,
    model_type: str = 'random_forest',
    hyperparams: Optional[Dict[str, Any]] = None
) -> Tuple[Any, Any, list]:
    """
    Train an ML model.
    
    Args:
        train_df: Training DataFrame with features and labels
        model_type: Type of model ('random_forest', 'logistic', etc.)
        hyperparams: Optional hyperparameter dict
        
    Returns:
        Tuple of (model, scaler, feature_columns)
    """
    logger.info(f"Training {model_type} model...")
    
    # Get feature columns
    feature_cols = get_feature_columns(train_df)
    logger.info(f"Using {len(feature_cols)} features")
    
    # Prepare data
    X_train = train_df[feature_cols].values
    y_train = train_df['label'].values
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    
    # Initialize model
    if hyperparams is None:
        hyperparams = {}
    
    if model_type == 'random_forest':
        model = RandomForestClassifier(
            n_estimators=hyperparams.get('n_estimators', 100),
            max_depth=hyperparams.get('max_depth', 10),
            min_samples_split=hyperparams.get('min_samples_split', 20),
            min_samples_leaf=hyperparams.get('min_samples_leaf', 10),
            random_state=hyperparams.get('random_state', 42),
            n_jobs=-1,
            class_weight='balanced'  # Handle class imbalance
        )
    elif model_type == 'logistic':
        model = LogisticRegression(
            C=hyperparams.get('C', 1.0),
            max_iter=hyperparams.get('max_iter', 1000),
            random_state=hyperparams.get('random_state', 42),
            class_weight='balanced',
            solver='lbfgs'
        )
    else:
        raise ValueError(f"Unsupported model type: {model_type}")
    
    # Train model
    logger.info("Training...")
    model.fit(X_train_scaled, y_train)
    logger.info("Training complete")
    
    return model, scaler, feature_cols


def evaluate_model(
    model: Any,
    scaler: Any,
    test_df: pd.DataFrame,
    feature_cols: list
) -> Dict[str, Any]:
    """
    Evaluate model performance on test set.
    
    Args:
        model: Trained model
        scaler: Fitted scaler
        test_df: Test DataFrame
        feature_cols: List of feature column names
        
    Returns:
        Dict with evaluation metrics
    """
    logger.info("Evaluating model...")
    
    # Prepare test data
    X_test = test_df[feature_cols].values
    y_test = test_df['label'].values
    
    # Scale features
    X_test_scaled = scaler.transform(X_test)
    
    # Predictions
    y_pred = model.predict(X_test_scaled)
    
    # Metrics
    accuracy = accuracy_score(y_test, y_pred)
    
    # Classification report
    report = classification_report(
        y_test,
        y_pred,
        target_names=['SHORT', 'FLAT', 'LONG'],
        output_dict=True,
        zero_division=0
    )
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    
    # Feature importance (if available)
    feature_importance = None
    if hasattr(model, 'feature_importances_'):
        feature_importance = dict(zip(feature_cols, model.feature_importances_))
        # Sort by importance
        feature_importance = dict(
            sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:20]
        )
    
    results = {
        'accuracy': accuracy,
        'classification_report': report,
        'confusion_matrix': cm.tolist(),
        'feature_importance': feature_importance,
        'test_samples': len(y_test)
    }
    
    logger.info(f"Test Accuracy: {accuracy:.4f}")
    logger.info(f"Classification Report:\n{classification_report(y_test, y_pred, target_names=['SHORT', 'FLAT', 'LONG'], zero_division=0)}")
    
    return results


def save_trained_model(
    model: Any,
    scaler: Any,
    feature_cols: list,
    name: str,
    metadata: Dict[str, Any]
) -> Path:
    """
    Save trained model with scaler and feature info.
    
    Args:
        model: Trained model
        scaler: Fitted scaler
        feature_cols: List of feature column names
        name: Model name
        metadata: Training metadata
        
    Returns:
        Path to saved model
    """
    # Bundle model with scaler and feature info
    model_bundle = {
        'model': model,
        'scaler': scaler,
        'feature_cols': feature_cols
    }
    
    # Add feature info to metadata
    metadata['n_features'] = len(feature_cols)
    metadata['feature_cols'] = feature_cols
    
    # Save
    path = save_model(model_bundle, name, metadata, overwrite=True)
    
    logger.info(f"Model saved: {name}")
    
    return path


def train_pipeline(
    data_filepath: str,
    model_name: str = 'baseline_rf',
    model_type: str = 'random_forest',
    prediction_horizon: int = 1,
    train_ratio: float = 0.8,
    hyperparams: Optional[Dict[str, Any]] = None,
    feature_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Complete training pipeline.
    
    Args:
        data_filepath: Path to OHLCV CSV
        model_name: Name for saved model
        model_type: Type of model to train
        prediction_horizon: Periods ahead to predict
        train_ratio: Train/test split
        hyperparams: Model hyperparameters
        feature_config: Feature engineering config
        
    Returns:
        Dict with model, metrics, and metadata
    """
    logger.info("="*60)
    logger.info("STARTING ML TRAINING PIPELINE")
    logger.info("="*60)
    
    # Load data
    data = load_training_data(data_filepath, prediction_horizon, train_ratio)
    
    # Build features
    data = build_features(data, feature_config)
    
    # Train model
    model, scaler, feature_cols = train_model(
        data['train'],
        model_type=model_type,
        hyperparams=hyperparams
    )
    
    # Evaluate
    metrics = evaluate_model(model, scaler, data['test'], feature_cols)
    
    # Prepare metadata
    metadata = {
        'model_type': model_type,
        'prediction_horizon': prediction_horizon,
        'train_ratio': train_ratio,
        'hyperparams': hyperparams or {},
        'feature_config': feature_config or {},
        'metrics': metrics,
        'train_samples': len(data['train']),
        'test_samples': len(data['test'])
    }
    
    # Save model
    save_trained_model(model, scaler, feature_cols, model_name, metadata)
    
    logger.info("="*60)
    logger.info("TRAINING PIPELINE COMPLETE")
    logger.info(f"Model: {model_name}")
    logger.info(f"Test Accuracy: {metrics['accuracy']:.4f}")
    logger.info("="*60)
    
    return {
        'model': model,
        'scaler': scaler,
        'feature_cols': feature_cols,
        'metrics': metrics,
        'metadata': metadata
    }


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python train.py <data_filepath> [model_name]")
        sys.exit(1)
    
    data_filepath = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else 'baseline_rf'
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    
    # Train
    result = train_pipeline(
        data_filepath=data_filepath,
        model_name=model_name,
        model_type='random_forest',
        hyperparams={
            'n_estimators': 100,
            'max_depth': 10,
            'min_samples_split': 20,
            'min_samples_leaf': 10
        }
    )
    
    print(f"\nModel saved as: {model_name}")
    print(f"Test Accuracy: {result['metrics']['accuracy']:.4f}")
