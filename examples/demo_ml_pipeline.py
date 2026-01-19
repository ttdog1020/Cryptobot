"""
MODULE 17: ML Pipeline Demo

Demonstrates ML pipeline with dummy data:
1. Generate synthetic OHLCV data
2. Build features
3. Train a simple model
4. Use MLStrategy for inference
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path

from ml_pipeline.train import train_pipeline
from ml_pipeline.features import build_feature_matrix
from strategies.ml_strategy import MLStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

logger = logging.getLogger(__name__)


def generate_dummy_data(n_samples: int = 1000) -> pd.DataFrame:
    """
    Generate realistic dummy OHLCV data.
    
    Args:
        n_samples: Number of candles to generate
        
    Returns:
        DataFrame with OHLCV data
    """
    logger.info(f"Generating {n_samples} dummy candles...")
    
    np.random.seed(42)
    
    # Generate timestamps
    dates = pd.date_range('2024-01-01', periods=n_samples, freq='5min')
    
    # Generate realistic price movements
    base_price = 50000.0
    volatility = 0.0015
    
    # Random walk with drift
    returns = np.random.randn(n_samples) * volatility
    returns[::100] += 0.005  # Add occasional jumps
    
    close_prices = base_price * (1 + returns).cumprod()
    
    # Generate OHLC from close
    df = pd.DataFrame({
        'timestamp': dates,
        'close': close_prices
    })
    
    # Open is close shifted
    df['open'] = df['close'].shift(1).fillna(base_price)
    
    # High and low based on close and open
    df['high'] = df[['open', 'close']].max(axis=1) * (1 + abs(np.random.randn(n_samples)) * 0.002)
    df['low'] = df[['open', 'close']].min(axis=1) * (1 - abs(np.random.randn(n_samples)) * 0.002)
    
    # Volume
    df['volume'] = np.random.uniform(50, 200, n_samples) * (1 + abs(df['close'].pct_change()) * 10)
    df['volume'] = df['volume'].fillna(100)
    
    logger.info(f"Generated data: {len(df)} candles, price range ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    
    return df


def demo_training():
    """Demonstrate model training on dummy data."""
    logger.info("="*60)
    logger.info("DEMO: ML MODEL TRAINING")
    logger.info("="*60)
    
    # Generate dummy data
    df = generate_dummy_data(n_samples=2000)
    
    # Save to CSV for training
    data_path = Path("dummy_data.csv")
    df.to_csv(data_path, index=False)
    logger.info(f"Saved dummy data to {data_path}")
    
    # Train model
    logger.info("\nTraining model...")
    result = train_pipeline(
        data_filepath=str(data_path),
        model_name='demo_ml_model',
        model_type='random_forest',
        prediction_horizon=1,
        train_ratio=0.8,
        hyperparams={
            'n_estimators': 50,  # Small for demo
            'max_depth': 8,
            'min_samples_split': 20,
            'min_samples_leaf': 10
        }
    )
    
    # Show results
    logger.info("\n" + "="*60)
    logger.info("TRAINING RESULTS")
    logger.info("="*60)
    logger.info(f"Model: demo_ml_model")
    logger.info(f"Test Accuracy: {result['metrics']['accuracy']:.4f}")
    logger.info(f"Features: {result['metrics']['test_samples']} test samples")
    
    # Show feature importance
    if result['metrics'].get('feature_importance'):
        logger.info("\nTop 10 Most Important Features:")
        for i, (feat, importance) in enumerate(list(result['metrics']['feature_importance'].items())[:10], 1):
            logger.info(f"  {i}. {feat}: {importance:.4f}")
    
    # Cleanup
    if data_path.exists():
        data_path.unlink()
    
    return result


def demo_inference():
    """Demonstrate ML inference with MLStrategy."""
    logger.info("\n" + "="*60)
    logger.info("DEMO: ML INFERENCE")
    logger.info("="*60)
    
    # Check if model exists
    from ml_pipeline.model_registry import list_models
    models = list_models()
    
    if not any(m['name'] == 'demo_ml_model' for m in models):
        logger.warning("Demo model not found. Running training first...")
        demo_training()
    
    # Load strategy
    logger.info("\nLoading MLStrategy...")
    strategy = MLStrategy(
        model_name='demo_ml_model',
        min_confidence=0.55
    )
    logger.info(f"Strategy loaded: {strategy}")
    
    # Generate test data
    logger.info("\nGenerating test data...")
    df = generate_dummy_data(n_samples=200)
    
    # Generate signals on last few candles
    logger.info("\nGenerating signals on recent data...")
    
    for i in range(-5, 0):  # Last 5 candles
        # Get data up to this point
        test_df = df.iloc[:len(df)+i].copy()
        
        # Generate signal
        result = strategy.generate_signal(test_df)
        
        signal = result['signal']
        metadata = result['metadata']
        
        logger.info(f"\nCandle {len(test_df)}:")
        logger.info(f"  Price: ${test_df['close'].iloc[-1]:.2f}")
        logger.info(f"  Signal: {signal}")
        
        if signal != 'FLAT':
            logger.info(f"  Confidence: {metadata.get('confidence', 0):.3f}")
            logger.info(f"  Entry: ${metadata.get('entry_price', 0):.2f}")
            logger.info(f"  SL Distance: ${metadata.get('sl_distance', 0):.2f}")
            logger.info(f"  TP Distance: ${metadata.get('tp_distance', 0):.2f}")
        else:
            logger.info(f"  Reason: {metadata.get('reason', 'N/A')}")


def demo_integration():
    """Demonstrate integration with RiskEngine."""
    logger.info("\n" + "="*60)
    logger.info("DEMO: RISKENGINE INTEGRATION")
    logger.info("="*60)
    
    # Import RiskEngine
    from risk_management import RiskEngine, RiskConfig
    
    # Load risk config
    risk_config = RiskConfig.from_file(Path("config/risk.json"))
    risk_engine = RiskEngine(risk_config)
    
    logger.info("RiskEngine loaded")
    
    # Load ML strategy
    strategy = MLStrategy(model_name='demo_ml_model', min_confidence=0.55)
    
    # Generate test data
    df = generate_dummy_data(n_samples=200)
    
    # Generate signal
    result = strategy.generate_signal(df)
    signal = result['signal']
    metadata = result['metadata']
    
    logger.info(f"\nML Signal: {signal}")
    
    if signal in ['LONG', 'SHORT']:
        # Apply risk engine
        entry_price = metadata['entry_price']
        sl_distance = metadata['sl_distance']
        tp_distance = metadata['tp_distance']
        
        if signal == 'LONG':
            sl_price = entry_price - sl_distance
            tp_price = entry_price + tp_distance
        else:
            sl_price = entry_price + sl_distance
            tp_price = entry_price - tp_distance
        
        # Get risk-managed order
        equity = 10000.0  # Demo equity
        order = risk_engine.apply_risk_to_signal(
            signal=signal,
            equity=equity,
            entry_price=entry_price,
            stop_loss_price=sl_price,
            take_profit_price=tp_price
        )
        
        if order:
            logger.info("\n[OK] Risk-Managed Order:")
            logger.info(f"  Signal: {order['side']}")
            logger.info(f"  Entry: ${order['entry_price']:.2f}")
            logger.info(f"  Position Size: {order['position_size']:.6f} units")
            logger.info(f"  Position Value: ${order['position_value_usd']:.2f}")
            logger.info(f"  Stop-Loss: ${order['stop_loss']:.2f}")
            logger.info(f"  Take-Profit: ${order['take_profit']:.2f}")
            logger.info(f"  Risk: ${order['risk_usd']:.2f} ({order['risk_usd']/equity*100:.2f}% of equity)")
        else:
            logger.warning("Order rejected by risk engine")
    else:
        logger.info("Signal is FLAT, no order to process")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("MODULE 17: ML PIPELINE DEMONSTRATION")
    print("="*60)
    
    # Run demos
    demo_training()
    demo_inference()
    demo_integration()
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("1. Train on real OHLCV data from your exchange")
    print("2. Use MLStrategy in backtesting: python backtest.py")
    print("3. Use MLStrategy in live runtime: modify run_live.py")
    print("4. Tune hyperparameters in config/ml.yaml")
    print("="*60)
