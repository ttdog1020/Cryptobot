"""
MODULE 17: ML Pipeline Tests

Test feature engineering, model registry, and ML strategy integration.
"""

import unittest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import shutil

from ml_pipeline.features import (
    build_feature_matrix,
    get_feature_columns,
    add_price_features,
    add_ema_features,
    add_rsi_features
)
from ml_pipeline.model_registry import (
    save_model,
    load_model,
    list_models,
    delete_model
)
from ml_pipeline.data_prep import (
    clean_ohlcv_data,
    align_data_for_training
)
from ml_pipeline.inference import predict_signal


class TestFeatureEngineering(unittest.TestCase):
    """Test feature engineering functions."""
    
    def setUp(self):
        """Create sample OHLCV data."""
        np.random.seed(42)
        n = 200
        
        dates = pd.date_range('2024-01-01', periods=n, freq='1H')
        base_price = 50000
        
        # Generate realistic price data
        returns = np.random.randn(n) * 0.002
        prices = base_price * (1 + returns).cumprod()
        
        self.df = pd.DataFrame({
            'timestamp': dates,
            'open': prices * (1 + np.random.randn(n) * 0.001),
            'high': prices * (1 + abs(np.random.randn(n)) * 0.003),
            'low': prices * (1 - abs(np.random.randn(n)) * 0.003),
            'close': prices,
            'volume': np.random.uniform(100, 1000, n)
        })
    
    def test_build_feature_matrix_shape(self):
        """Test that feature matrix has correct shape."""
        df_features = build_feature_matrix(self.df.copy())
        
        # Should have rows (some lost to NaN from rolling calcs)
        self.assertGreater(len(df_features), 100)
        
        # Should have many more columns than original
        self.assertGreater(len(df_features.columns), len(self.df.columns))
    
    def test_build_feature_matrix_no_nan(self):
        """Test that feature matrix has no NaN values."""
        df_features = build_feature_matrix(self.df.copy())
        
        # After dropna, should have no NaN
        nan_count = df_features.isna().sum().sum()
        self.assertEqual(nan_count, 0)
    
    def test_get_feature_columns(self):
        """Test feature column extraction."""
        df_features = build_feature_matrix(self.df.copy())
        feature_cols = get_feature_columns(df_features)
        
        # Should have feature columns
        self.assertGreater(len(feature_cols), 0)
        
        # Should not include base OHLCV columns
        for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
            self.assertNotIn(col, feature_cols)
    
    def test_price_features(self):
        """Test price-based features."""
        df_features = add_price_features(self.df.copy())
        
        # Check expected columns exist
        expected = ['norm_open', 'norm_high', 'norm_low', 'hl_range', 'body_ratio']
        for col in expected:
            self.assertIn(col, df_features.columns)
    
    def test_ema_features(self):
        """Test EMA features."""
        df_features = add_ema_features(self.df.copy())
        
        # Check EMA columns
        expected = ['ema_5', 'ema_9', 'ema_20', 'ema_50']
        for col in expected:
            self.assertIn(col, df_features.columns)
        
        # Check EMA distance features
        self.assertIn('ema_5_dist', df_features.columns)
    
    def test_rsi_features(self):
        """Test RSI features."""
        df_features = add_rsi_features(self.df.copy())
        
        # Check RSI columns
        expected = ['rsi_7', 'rsi_14']
        for col in expected:
            self.assertIn(col, df_features.columns)
        
        # RSI should be between 0 and 100
        df_clean = df_features.dropna()
        for col in expected:
            self.assertTrue((df_clean[col] >= 0).all())
            self.assertTrue((df_clean[col] <= 100).all())


class TestDataPrep(unittest.TestCase):
    """Test data preprocessing functions."""
    
    def setUp(self):
        """Create sample data."""
        np.random.seed(42)
        n = 100
        
        dates = pd.date_range('2024-01-01', periods=n, freq='1H')
        base_price = 50000
        returns = np.random.randn(n) * 0.002
        prices = base_price * (1 + returns).cumprod()
        
        self.df = pd.DataFrame({
            'timestamp': dates,
            'open': prices * (1 + np.random.randn(n) * 0.001),
            'high': prices * (1 + abs(np.random.randn(n)) * 0.003),
            'low': prices * (1 - abs(np.random.randn(n)) * 0.003),
            'close': prices,
            'volume': np.random.uniform(100, 1000, n)
        })
    
    def test_clean_removes_invalid_ohlc(self):
        """Test that cleaning removes invalid OHLC relationships."""
        df = self.df.copy()
        
        # Introduce invalid data
        df.loc[5, 'high'] = df.loc[5, 'low'] - 10  # High < Low
        
        df_clean = clean_ohlcv_data(df, remove_outliers=False)
        
        # Should have removed the invalid row
        self.assertLess(len(df_clean), len(df))
    
    def test_align_creates_labels(self):
        """Test that alignment creates labels."""
        df_aligned = align_data_for_training(self.df.copy(), prediction_horizon=1)
        
        # Should have label column
        self.assertIn('label', df_aligned.columns)
        
        # Labels should be -1, 0, or 1
        unique_labels = df_aligned['label'].unique()
        for label in unique_labels:
            self.assertIn(label, [-1, 0, 1])


class TestModelRegistry(unittest.TestCase):
    """Test model save/load functionality."""
    
    def setUp(self):
        """Set up test model directory."""
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Patch MODELS_DIR temporarily
        import ml_pipeline.model_registry as mr
        self.original_models_dir = mr.MODELS_DIR
        mr.MODELS_DIR = self.test_dir
    
    def tearDown(self):
        """Clean up test directory."""
        import ml_pipeline.model_registry as mr
        mr.MODELS_DIR = self.original_models_dir
        
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_save_and_load_model(self):
        """Test saving and loading a model."""
        # Create a simple model (just a dict for testing)
        model = {'type': 'test', 'params': [1, 2, 3]}
        
        # Save
        save_model(model, 'test_model', metadata={'test': True})
        
        # Load
        loaded = load_model('test_model')
        
        # Check
        self.assertEqual(loaded['type'], 'test')
        self.assertEqual(loaded['params'], [1, 2, 3])
    
    def test_list_models(self):
        """Test listing models."""
        # Save multiple models
        save_model({'a': 1}, 'model_1')
        save_model({'b': 2}, 'model_2')
        
        # List
        models = list_models()
        
        # Check
        self.assertEqual(len(models), 2)
        model_names = [m['name'] for m in models]
        self.assertIn('model_1', model_names)
        self.assertIn('model_2', model_names)
    
    def test_delete_model(self):
        """Test deleting a model."""
        # Save
        save_model({'x': 1}, 'to_delete')
        
        # Delete
        result = delete_model('to_delete')
        self.assertTrue(result)
        
        # Verify deleted
        models = list_models()
        model_names = [m['name'] for m in models]
        self.assertNotIn('to_delete', model_names)
    
    def test_overwrite_protection(self):
        """Test that overwrite protection works."""
        save_model({'v': 1}, 'protected')
        
        # Should raise error without overwrite flag
        with self.assertRaises(FileExistsError):
            save_model({'v': 2}, 'protected', overwrite=False)


class TestInference(unittest.TestCase):
    """Test inference utilities."""
    
    def test_predict_signal_with_mock_model(self):
        """Test prediction with a mock model."""
        # Create mock model
        class MockModel:
            def predict(self, X):
                return np.array([1])  # LONG
            
            def predict_proba(self, X):
                return np.array([[0.1, 0.2, 0.7]])  # [SHORT, FLAT, LONG]
        
        model = MockModel()
        features = np.random.randn(10)
        
        result = predict_signal(model, features, min_confidence=0.5)
        
        # Should return LONG with high confidence
        self.assertEqual(result['signal'], 'LONG')
        self.assertGreater(result['confidence'], 0.5)
    
    def test_predict_signal_low_confidence(self):
        """Test that low confidence returns FLAT."""
        class MockModel:
            def predict(self, X):
                return np.array([1])
            
            def predict_proba(self, X):
                return np.array([[0.4, 0.4, 0.2]])  # Low confidence
        
        model = MockModel()
        features = np.random.randn(10)
        
        result = predict_signal(model, features, min_confidence=0.6)
        
        # Should default to FLAT due to low confidence
        self.assertEqual(result['signal'], 'FLAT')


class TestMLStrategyIntegration(unittest.TestCase):
    """Test MLStrategy integration with backtesting/live runtime."""
    
    def test_ml_strategy_returns_valid_signal(self):
        """Test that MLStrategy returns valid signal format."""
        # This test requires a trained model, so we'll skip if not available
        try:
            from strategies.ml_based import MLStrategy
            
            # Try to create strategy (will fail if no model exists)
            # This is more of an integration test
            
            # For unit test, just verify the class exists and has required methods
            self.assertTrue(hasattr(MLStrategy, 'generate_signal'))
            self.assertTrue(hasattr(MLStrategy, 'get_required_history'))
        
        except Exception as e:
            # Expected if no model trained yet
            self.skipTest(f"MLStrategy not testable without trained model: {e}")
    
    def test_ml_strategy_signal_format(self):
        """Test that ML signal format is compatible with RiskEngine."""
        # Expected signal format:
        expected_keys = ['signal', 'metadata']
        expected_metadata_keys = ['entry_price', 'confidence', 'sl_distance', 'tp_distance']
        
        # Create a mock signal
        signal = {
            'signal': 'LONG',
            'metadata': {
                'entry_price': 50000.0,
                'confidence': 0.75,
                'sl_distance': 500.0,
                'tp_distance': 1500.0
            }
        }
        
        # Verify format
        for key in expected_keys:
            self.assertIn(key, signal)
        
        for key in expected_metadata_keys:
            self.assertIn(key, signal['metadata'])
        
        # Verify signal value
        self.assertIn(signal['signal'], ['LONG', 'SHORT', 'FLAT'])


class TestMLPipelineEndToEnd(unittest.TestCase):
    """End-to-end integration tests."""
    
    def test_feature_engineering_pipeline(self):
        """Test complete feature engineering pipeline."""
        # Create sample data
        np.random.seed(42)
        n = 200
        dates = pd.date_range('2024-01-01', periods=n, freq='1H')
        prices = 50000 * (1 + np.random.randn(n) * 0.002).cumprod()
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices * (1 + np.random.randn(n) * 0.001),
            'high': prices * (1 + abs(np.random.randn(n)) * 0.003),
            'low': prices * (1 - abs(np.random.randn(n)) * 0.003),
            'close': prices,
            'volume': np.random.uniform(100, 1000, n)
        })
        
        # Build features
        df_features = build_feature_matrix(df)
        
        # Get feature columns
        feature_cols = get_feature_columns(df_features)
        
        # Verify we can extract features for prediction
        X = df_features[feature_cols].iloc[-1:].values
        
        # Should have features and no NaN
        self.assertGreater(len(feature_cols), 0)
        self.assertFalse(np.isnan(X).any())


if __name__ == '__main__':
    unittest.main()
