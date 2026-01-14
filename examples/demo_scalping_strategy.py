"""
Demonstration of the Scalping EMA-RSI Strategy

Shows examples of LONG and SHORT signal generation with mock data.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from strategies.rule_based.scalping.scalping_ema_rsi import ScalpingEMARSI


def create_trending_up_data(n_bars: int = 100) -> pd.DataFrame:
    """Create data with upward trend and bullish EMA cross."""
    np.random.seed(100)
    
    timestamps = pd.date_range(start="2024-01-01", periods=n_bars, freq="1min")
    data = {
        "timestamp": timestamps,
        "open": [],
        "high": [],
        "low": [],
        "close": [],
        "volume": []
    }
    
    # Create data with downtrend then sharp uptrend (to force cross)
    base_price = 100.0
    for i in range(n_bars):
        if i < 50:
            # Slight downtrend first
            trend = -i * 0.05
        else:
            # Sharp uptrend to force EMA5 above EMA9
            trend = -(50 * 0.05) + (i - 50) * 0.3
        
        noise = np.random.randn() * 0.1
        close_price = base_price + trend + noise
        
        open_price = close_price - 0.05 + np.random.randn() * 0.05
        high_price = max(open_price, close_price) + abs(np.random.randn() * 0.1)
        low_price = min(open_price, close_price) - abs(np.random.randn() * 0.1)
        
        # Normal volume with spike at the end
        if i >= n_bars - 2:
            volume = 2000 + np.random.randint(-100, 100)  # Volume spike
        else:
            volume = 1000 + np.random.randint(-100, 100)
        
        data["open"].append(open_price)
        data["high"].append(high_price)
        data["low"].append(low_price)
        data["close"].append(close_price)
        data["volume"].append(volume)
    
    return pd.DataFrame(data)


def create_trending_down_data(n_bars: int = 100) -> pd.DataFrame:
    """Create data with downward trend and bearish EMA cross."""
    np.random.seed(200)
    
    timestamps = pd.date_range(start="2024-01-01", periods=n_bars, freq="1min")
    data = {
        "timestamp": timestamps,
        "open": [],
        "high": [],
        "low": [],
        "close": [],
        "volume": []
    }
    
    # Create data with uptrend then sharp downtrend (to force cross)
    base_price = 110.0
    for i in range(n_bars):
        if i < 50:
            # Slight uptrend first
            trend = i * 0.05
        else:
            # Sharp downtrend to force EMA5 below EMA9
            trend = (50 * 0.05) - (i - 50) * 0.3
        
        noise = np.random.randn() * 0.1
        close_price = base_price + trend + noise
        
        open_price = close_price + 0.05 + np.random.randn() * 0.05
        high_price = max(open_price, close_price) + abs(np.random.randn() * 0.1)
        low_price = min(open_price, close_price) - abs(np.random.randn() * 0.1)
        
        # Normal volume with spike at the end
        if i >= n_bars - 2:
            volume = 2000 + np.random.randint(-100, 100)  # Volume spike
        else:
            volume = 1000 + np.random.randint(-100, 100)
        
        data["open"].append(open_price)
        data["high"].append(high_price)
        data["low"].append(low_price)
        data["close"].append(close_price)
        data["volume"].append(volume)
    
    return pd.DataFrame(data)


def demonstrate_long_signal():
    """Demonstrate LONG signal generation."""
    print("\n" + "="*60)
    print("LONG SIGNAL DEMONSTRATION")
    print("="*60)
    
    # Create bullish data
    df = create_trending_up_data(100)
    
    # Initialize strategy with relaxed parameters for demo
    strategy = ScalpingEMARSI(config={
        "atr_min_threshold": 0.01,  # Very low for demo
        "rsi_long_min": 40,
        "rsi_long_max": 95,  # Allow higher RSI
        "rsi_extreme_high": 101,  # Disable extreme filter for demo
        "volume_multiplier": 1.3
    })
    
    # Add indicators
    df = strategy.add_indicators(df)
    
    # Generate signal
    result = strategy.generate_signal(df)
    
    # Display results
    last_bar = df.iloc[-1]
    print(f"\nMarket Conditions:")
    print(f"  Price: ${last_bar['close']:.2f}")
    print(f"  EMA5: ${last_bar['ema_fast']:.2f}")
    print(f"  EMA9: ${last_bar['ema_slow']:.2f}")
    print(f"  EMA5 > EMA9: {last_bar['ema_fast'] > last_bar['ema_slow']}")
    print(f"  RSI(7): {last_bar['rsi']:.2f}")
    print(f"  ATR: ${last_bar['atr']:.4f}")
    print(f"  Volume: {last_bar['volume']:.0f}")
    print(f"  Volume Avg: {last_bar['volume_avg']:.0f}")
    print(f"  Volume Spike: {last_bar['volume_spike']}")
    
    print(f"\nSignal Generated: {result['signal']}")
    print(f"\nMetadata:")
    for key, value in result['metadata'].items():
        if isinstance(value, (int, float, np.number)):
            print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")
        else:
            print(f"  {key}: {value}")
    
    if result['signal'] == "LONG":
        print(f"\n✓ LONG SIGNAL TRIGGERED!")
        print(f"  Entry Price: ${result['metadata']['entry_price']:.2f}")
        print(f"  Stop-Loss Distance: ${result['metadata']['sl_distance']:.4f}")
        print(f"  Take-Profit Distance: ${result['metadata']['tp_distance']:.4f}")
        
        sl_price = result['metadata']['entry_price'] - result['metadata']['sl_distance']
        tp_price = result['metadata']['entry_price'] + result['metadata']['tp_distance']
        
        print(f"  → Stop-Loss Price: ${sl_price:.2f}")
        print(f"  → Take-Profit Price: ${tp_price:.2f}")
        
        risk_reward = result['metadata']['tp_distance'] / result['metadata']['sl_distance']
        print(f"  → Risk:Reward Ratio: 1:{risk_reward:.2f}")
    else:
        print(f"\n✗ No LONG signal (reason: {result['metadata'].get('reason', 'unknown')})")


def demonstrate_short_signal():
    """Demonstrate SHORT signal generation."""
    print("\n" + "="*60)
    print("SHORT SIGNAL DEMONSTRATION")
    print("="*60)
    
    # Create bearish data
    df = create_trending_down_data(100)
    
    # Initialize strategy with relaxed parameters for demo
    strategy = ScalpingEMARSI(config={
        "atr_min_threshold": 0.01,  # Very low for demo
        "rsi_short_min": 5,  # Allow lower RSI
        "rsi_short_max": 60,
        "rsi_extreme_low": -1,  # Disable extreme filter for demo
        "volume_multiplier": 1.3
    })
    
    # Add indicators
    df = strategy.add_indicators(df)
    
    # Show last few EMA values to see crossover
    print(f"\nLast 5 bars EMA values:")
    for i in range(len(df) - 5, len(df)):
        row = df.iloc[i]
        cross_here = "← BEARISH CROSS" if i > 0 and df.iloc[i-1]['ema_fast'] >= df.iloc[i-1]['ema_slow'] and row['ema_fast'] < row['ema_slow'] else ""
        print(f"  Bar {i}: EMA5={row['ema_fast']:.2f}, EMA9={row['ema_slow']:.2f} {cross_here}")
    
    # Generate signal
    result = strategy.generate_signal(df)
    
    # Display results
    last_bar = df.iloc[-1]
    print(f"\nMarket Conditions:")
    print(f"  Price: ${last_bar['close']:.2f}")
    print(f"  EMA5: ${last_bar['ema_fast']:.2f}")
    print(f"  EMA9: ${last_bar['ema_slow']:.2f}")
    print(f"  EMA5 < EMA9: {last_bar['ema_fast'] < last_bar['ema_slow']}")
    print(f"  RSI(7): {last_bar['rsi']:.2f}")
    print(f"  ATR: ${last_bar['atr']:.4f}")
    print(f"  Volume: {last_bar['volume']:.0f}")
    print(f"  Volume Avg: {last_bar['volume_avg']:.0f}")
    print(f"  Volume Spike: {last_bar['volume_spike']}")
    
    print(f"\nSignal Generated: {result['signal']}")
    print(f"\nMetadata:")
    for key, value in result['metadata'].items():
        if isinstance(value, (int, float, np.number)):
            print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")
        else:
            print(f"  {key}: {value}")
    
    if result['signal'] == "SHORT":
        print(f"\n✓ SHORT SIGNAL TRIGGERED!")
        print(f"  Entry Price: ${result['metadata']['entry_price']:.2f}")
        print(f"  Stop-Loss Distance: ${result['metadata']['sl_distance']:.4f}")
        print(f"  Take-Profit Distance: ${result['metadata']['tp_distance']:.4f}")
        
        sl_price = result['metadata']['entry_price'] + result['metadata']['sl_distance']
        tp_price = result['metadata']['entry_price'] - result['metadata']['tp_distance']
        
        print(f"  → Stop-Loss Price: ${sl_price:.2f}")
        print(f"  → Take-Profit Price: ${tp_price:.2f}")
        
        risk_reward = result['metadata']['tp_distance'] / result['metadata']['sl_distance']
        print(f"  → Risk:Reward Ratio: 1:{risk_reward:.2f}")
    else:
        print(f"\n✗ No SHORT signal (reason: {result['metadata'].get('reason', 'unknown')})")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SCALPING STRATEGY DEMONSTRATION")
    print("Strategy: EMA(5/9) + RSI(7) + Volume Spike")
    print("="*60)
    
    demonstrate_long_signal()
    demonstrate_short_signal()
    
    print("\n" + "="*60)
    print("DEMONSTRATION COMPLETE")
    print("="*60)
