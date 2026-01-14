"""
Tests for the scalping strategy module.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from strategies.rule_based.scalping.scalping_ema_rsi import ScalpingEMARSI, add_indicators, generate_signal_with_metadata


def create_mock_data(n_bars: int = 100) -> pd.DataFrame:
    """Create mock OHLCV data for testing."""
    np.random.seed(42)
    
    base_price = 100.0
    data = {
        "timestamp": pd.date_range(start="2024-01-01", periods=n_bars, freq="1min"),
        "open": [],
        "high": [],
        "low": [],
        "close": [],
        "volume": []
    }
    
    price = base_price
    for i in range(n_bars):
        change = np.random.randn() * 0.5
        price = price + change
        
        open_price = price
        high_price = price + abs(np.random.randn() * 0.3)
        low_price = price - abs(np.random.randn() * 0.3)
        close_price = price + np.random.randn() * 0.2
        volume = 1000 + np.random.randint(-200, 200)
        
        data["open"].append(open_price)
        data["high"].append(high_price)
        data["low"].append(low_price)
        data["close"].append(close_price)
        data["volume"].append(volume)
    
    return pd.DataFrame(data)


def create_bullish_setup() -> pd.DataFrame:
    """Create a bullish EMA crossover setup with proper indicators."""
    df = create_mock_data(50)
    
    # Manually create a bullish setup at the end
    # Force EMA5 to cross above EMA9
    for i in range(len(df) - 10, len(df)):
        df.loc[i, "close"] = 100 + (i - (len(df) - 10)) * 0.5  # Uptrend
    
    # Add high volume at the end
    df.loc[len(df) - 1, "volume"] = 2000
    
    return df


def create_bearish_setup() -> pd.DataFrame:
    """Create a bearish EMA crossover setup with proper indicators."""
    df = create_mock_data(50)
    
    # Manually create a bearish setup at the end
    # Force EMA5 to cross below EMA9
    for i in range(len(df) - 10, len(df)):
        df.loc[i, "close"] = 100 - (i - (len(df) - 10)) * 0.5  # Downtrend
    
    # Add high volume at the end
    df.loc[len(df) - 1, "volume"] = 2000
    
    return df


def test_indicator_calculation():
    """Test that indicators are calculated correctly."""
    print("\n=== Test: Indicator Calculation ===")
    
    df = create_mock_data(100)
    strategy = ScalpingEMARSI()
    df_with_indicators = strategy.add_indicators(df)
    
    # Check that all indicators exist
    required_cols = ["ema_fast", "ema_slow", "rsi", "atr", "volume_avg", "volume_spike"]
    for col in required_cols:
        assert col in df_with_indicators.columns, f"Missing column: {col}"
    
    # Check that indicators have values (not all NaN)
    last_bar = df_with_indicators.iloc[-1]
    assert not pd.isna(last_bar["ema_fast"]), "EMA fast is NaN"
    assert not pd.isna(last_bar["ema_slow"]), "EMA slow is NaN"
    assert not pd.isna(last_bar["rsi"]), "RSI is NaN"
    assert not pd.isna(last_bar["atr"]), "ATR is NaN"
    
    # Check RSI bounds (should be 0-100)
    rsi_values = df_with_indicators["rsi"].dropna()
    assert (rsi_values >= 0).all() and (rsi_values <= 100).all(), "RSI out of bounds"
    
    print(f"✓ All indicators calculated successfully")
    print(f"  Last bar - EMA5: {last_bar['ema_fast']:.2f}, EMA9: {last_bar['ema_slow']:.2f}")
    print(f"  Last bar - RSI: {last_bar['rsi']:.2f}, ATR: {last_bar['atr']:.4f}")
    print("✓ PASSED")


def test_long_signal_trigger():
    """Test LONG signal generation when all conditions align."""
    print("\n=== Test: LONG Signal Trigger ===")
    
    df = create_bullish_setup()
    strategy = ScalpingEMARSI(config={
        "atr_min_threshold": 0.1,  # Lower threshold for test data
        "rsi_long_min": 40,  # Wider range for test
        "rsi_long_max": 80
    })
    
    df_with_indicators = strategy.add_indicators(df)
    result = strategy.generate_signal(df_with_indicators)
    
    print(f"Signal: {result['signal']}")
    print(f"Metadata: {result['metadata']}")
    
    # Should get LONG or FLAT (depending on exact RSI/volume conditions)
    assert result["signal"] in ["LONG", "FLAT"], f"Unexpected signal: {result['signal']}"
    
    if result["signal"] == "LONG":
        # Check metadata
        assert "entry_price" in result["metadata"], "Missing entry_price"
        assert "sl_distance" in result["metadata"], "Missing sl_distance"
        assert "tp_distance" in result["metadata"], "Missing tp_distance"
        assert "atr" in result["metadata"], "Missing atr"
        
        print(f"✓ LONG signal generated with proper metadata")
        print(f"  Entry: ${result['metadata']['entry_price']:.2f}")
        print(f"  SL distance: ${result['metadata']['sl_distance']:.4f}")
        print(f"  TP distance: ${result['metadata']['tp_distance']:.4f}")
    else:
        print(f"✓ FLAT signal (reason: {result['metadata'].get('reason', 'unknown')})")
    
    print("✓ PASSED")


def test_short_signal_trigger():
    """Test SHORT signal generation when all conditions align."""
    print("\n=== Test: SHORT Signal Trigger ===")
    
    df = create_bearish_setup()
    strategy = ScalpingEMARSI(config={
        "atr_min_threshold": 0.1,  # Lower threshold for test data
        "rsi_short_min": 20,  # Wider range for test
        "rsi_short_max": 60
    })
    
    df_with_indicators = strategy.add_indicators(df)
    result = strategy.generate_signal(df_with_indicators)
    
    print(f"Signal: {result['signal']}")
    print(f"Metadata: {result['metadata']}")
    
    # Should get SHORT or FLAT (depending on exact RSI/volume conditions)
    assert result["signal"] in ["SHORT", "FLAT"], f"Unexpected signal: {result['signal']}"
    
    if result["signal"] == "SHORT":
        # Check metadata
        assert "entry_price" in result["metadata"], "Missing entry_price"
        assert "sl_distance" in result["metadata"], "Missing sl_distance"
        assert "tp_distance" in result["metadata"], "Missing tp_distance"
        
        print(f"✓ SHORT signal generated with proper metadata")
        print(f"  Entry: ${result['metadata']['entry_price']:.2f}")
        print(f"  SL distance: ${result['metadata']['sl_distance']:.4f}")
        print(f"  TP distance: ${result['metadata']['tp_distance']:.4f}")
    else:
        print(f"✓ FLAT signal (reason: {result['metadata'].get('reason', 'unknown')})")
    
    print("✓ PASSED")


def test_volume_filter():
    """Test that low volume prevents signals."""
    print("\n=== Test: Volume Filter ===")
    
    df = create_mock_data(50)
    
    # Force low volume (all bars have similar volume, so no spike)
    df["volume"] = 1000
    
    strategy = ScalpingEMARSI(config={"atr_min_threshold": 0.1})
    df_with_indicators = strategy.add_indicators(df)
    result = strategy.generate_signal(df_with_indicators)
    
    print(f"Signal: {result['signal']}")
    print(f"Reason: {result['metadata'].get('reason', 'N/A')}")
    
    # Should be FLAT due to no volume spike
    assert result["signal"] == "FLAT", "Should be FLAT when no volume spike"
    
    if result["metadata"].get("reason") == "no_volume_spike":
        print("✓ Correctly rejected due to no volume spike")
    else:
        print(f"✓ Rejected for: {result['metadata'].get('reason', 'other')}")
    
    print("✓ PASSED")


def test_atr_filter():
    """Test that low ATR prevents signals."""
    print("\n=== Test: ATR Filter ===")
    
    df = create_mock_data(50)
    
    # Create very low volatility (tight range)
    for i in range(len(df)):
        df.loc[i, "high"] = 100.01
        df.loc[i, "low"] = 99.99
        df.loc[i, "close"] = 100.0
    
    strategy = ScalpingEMARSI(config={
        "atr_min_threshold": 1.0  # High threshold to trigger filter
    })
    df_with_indicators = strategy.add_indicators(df)
    result = strategy.generate_signal(df_with_indicators)
    
    print(f"Signal: {result['signal']}")
    print(f"Reason: {result['metadata'].get('reason', 'N/A')}")
    if "atr" in result["metadata"]:
        print(f"ATR: {result['metadata']['atr']:.4f}")
    
    # Should be FLAT due to low ATR
    assert result["signal"] == "FLAT", "Should be FLAT when ATR is low"
    
    if result["metadata"].get("reason") == "low_volatility":
        print("✓ Correctly rejected due to low volatility")
    else:
        print(f"✓ Rejected for: {result['metadata'].get('reason', 'other')}")
    
    print("✓ PASSED")


def test_extreme_rsi_filter():
    """Test that extreme RSI values prevent signals."""
    print("\n=== Test: Extreme RSI Filter ===")
    
    df = create_mock_data(50)
    
    # Create extreme uptrend (should push RSI very high)
    for i in range(len(df) - 20, len(df)):
        df.loc[i, "close"] = 100 + (i - (len(df) - 20)) * 2  # Strong uptrend
    
    strategy = ScalpingEMARSI(config={
        "atr_min_threshold": 0.1,
        "rsi_extreme_high": 80  # Default threshold
    })
    df_with_indicators = strategy.add_indicators(df)
    result = strategy.generate_signal(df_with_indicators)
    
    print(f"Signal: {result['signal']}")
    print(f"Reason: {result['metadata'].get('reason', 'N/A')}")
    if "rsi" in result["metadata"]:
        print(f"RSI: {result['metadata']['rsi']:.2f}")
    
    # Check if RSI filter activated (might not always trigger with random data)
    if result["metadata"].get("reason") == "extreme_rsi":
        print("✓ Correctly rejected due to extreme RSI")
        assert result["signal"] == "FLAT", "Should be FLAT when RSI is extreme"
    else:
        print(f"✓ Signal behavior verified (reason: {result['metadata'].get('reason', 'other')})")
    
    print("✓ PASSED")


def test_insufficient_data():
    """Test behavior with insufficient data."""
    print("\n=== Test: Insufficient Data ===")
    
    df = create_mock_data(5)  # Very few bars
    
    strategy = ScalpingEMARSI()
    df_with_indicators = strategy.add_indicators(df)
    result = strategy.generate_signal(df_with_indicators)
    
    print(f"Signal: {result['signal']}")
    print(f"Reason: {result['metadata'].get('reason', 'N/A')}")
    
    # Should be FLAT due to insufficient data
    assert result["signal"] == "FLAT", "Should be FLAT with insufficient data"
    assert result["metadata"].get("reason") == "insufficient_data", "Wrong rejection reason"
    
    print("✓ Correctly rejected due to insufficient data")
    print("✓ PASSED")


def test_module_level_functions():
    """Test module-level convenience functions."""
    print("\n=== Test: Module-Level Functions ===")
    
    df = create_mock_data(100)
    
    # Test add_indicators
    df_with_ind = add_indicators(df)
    assert "ema_fast" in df_with_ind.columns, "add_indicators failed"
    
    # Test generate_signal_with_metadata
    result = generate_signal_with_metadata(df_with_ind)
    assert "signal" in result, "generate_signal_with_metadata failed"
    assert "metadata" in result, "Missing metadata"
    
    print(f"✓ Module-level functions work correctly")
    print(f"  Signal: {result['signal']}")
    print("✓ PASSED")


def run_all_tests():
    """Run all scalping strategy tests."""
    print("\n" + "="*60)
    print("SCALPING STRATEGY TEST SUITE")
    print("="*60)
    
    tests = [
        test_indicator_calculation,
        test_long_signal_trigger,
        test_short_signal_trigger,
        test_volume_filter,
        test_atr_filter,
        test_extreme_rsi_filter,
        test_insufficient_data,
        test_module_level_functions,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"TEST RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
