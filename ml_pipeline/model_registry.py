"""
MODULE 17: Model Registry

Save, load, and manage trained ML models.
"""

import joblib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Model storage directory
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)


def save_model(
    model: Any,
    name: str,
    metadata: Optional[Dict[str, Any]] = None,
    overwrite: bool = False
) -> Path:
    """
    Save a trained model to disk.
    
    Args:
        model: Trained model object (sklearn, pytorch, etc.)
        name: Model name (without extension)
        metadata: Optional metadata dict (hyperparameters, metrics, etc.)
        overwrite: Whether to overwrite existing model
        
    Returns:
        Path to saved model file
    """
    model_path = MODELS_DIR / f"{name}.pkl"
    metadata_path = MODELS_DIR / f"{name}_metadata.json"
    
    # Check if model exists
    if model_path.exists() and not overwrite:
        raise FileExistsError(
            f"Model '{name}' already exists. Set overwrite=True to replace it."
        )
    
    # Save model
    try:
        joblib.dump(model, model_path)
        logger.info(f"Model saved to {model_path}")
    except Exception as e:
        logger.error(f"Error saving model: {e}")
        raise
    
    # Save metadata
    if metadata is None:
        metadata = {}
    
    # Add timestamp
    metadata['saved_at'] = datetime.now().isoformat()
    metadata['model_name'] = name
    
    try:
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Metadata saved to {metadata_path}")
    except Exception as e:
        logger.warning(f"Error saving metadata: {e}")
    
    return model_path


def load_model(name: str) -> Any:
    """
    Load a trained model from disk.
    
    Args:
        name: Model name (without extension)
        
    Returns:
        Loaded model object
    """
    model_path = MODELS_DIR / f"{name}.pkl"
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model '{name}' not found at {model_path}")
    
    try:
        model = joblib.load(model_path)
        logger.info(f"Model loaded from {model_path}")
        return model
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        raise


def load_metadata(name: str) -> Optional[Dict[str, Any]]:
    """
    Load model metadata.
    
    Args:
        name: Model name (without extension)
        
    Returns:
        Metadata dict or None if not found
    """
    metadata_path = MODELS_DIR / f"{name}_metadata.json"
    
    if not metadata_path.exists():
        logger.warning(f"Metadata not found for model '{name}'")
        return None
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        return metadata
    except Exception as e:
        logger.warning(f"Error loading metadata: {e}")
        return None


def list_models() -> List[Dict[str, Any]]:
    """
    List all available models.
    
    Returns:
        List of dicts with model info (name, path, metadata)
    """
    models = []
    
    for model_file in MODELS_DIR.glob("*.pkl"):
        name = model_file.stem
        
        # Load metadata if available
        metadata = load_metadata(name)
        
        model_info = {
            'name': name,
            'path': str(model_file),
            'size_mb': model_file.stat().st_size / (1024 * 1024),
            'modified': datetime.fromtimestamp(model_file.stat().st_mtime).isoformat()
        }
        
        if metadata:
            model_info['metadata'] = metadata
        
        models.append(model_info)
    
    # Sort by modification time (newest first)
    models.sort(key=lambda x: x['modified'], reverse=True)
    
    return models


def delete_model(name: str) -> bool:
    """
    Delete a model and its metadata.
    
    Args:
        name: Model name (without extension)
        
    Returns:
        True if deleted successfully
    """
    model_path = MODELS_DIR / f"{name}.pkl"
    metadata_path = MODELS_DIR / f"{name}_metadata.json"
    
    deleted = False
    
    if model_path.exists():
        model_path.unlink()
        logger.info(f"Deleted model: {model_path}")
        deleted = True
    
    if metadata_path.exists():
        metadata_path.unlink()
        logger.info(f"Deleted metadata: {metadata_path}")
    
    if not deleted:
        logger.warning(f"Model '{name}' not found")
    
    return deleted


def get_model_info(name: str) -> Dict[str, Any]:
    """
    Get detailed information about a model.
    
    Args:
        name: Model name (without extension)
        
    Returns:
        Dict with model information
    """
    model_path = MODELS_DIR / f"{name}.pkl"
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model '{name}' not found")
    
    metadata = load_metadata(name)
    
    info = {
        'name': name,
        'path': str(model_path),
        'size_mb': model_path.stat().st_size / (1024 * 1024),
        'created': datetime.fromtimestamp(model_path.stat().st_ctime).isoformat(),
        'modified': datetime.fromtimestamp(model_path.stat().st_mtime).isoformat(),
        'metadata': metadata
    }
    
    return info
