"""
Tests for the centralized risk management engine.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from risk_management import RiskConfig, RiskEngine


def test_position_size_calculation():
    """Test basic position size calculation for LONG trades."""
    print("\n=== Test: Position Size Calculation ===")
    
    config = RiskConfig(
        default_risk_per_trade=0.02,  # 2% risk
        min_position_size_usd=10.0
    )
    engine = RiskEngine(config)
    
    # Test case: $1000 account, entry at $100, SL at $95 (5% SL distance)
    equity = 1000.0
    entry_price = 100.0
    stop_loss_price = 95.0
    
    position_size = engine.compute_position_size(equity, entry_price, stop_loss_price)
    
    # Expected: (1000 * 0.02) / (100 - 95) = 20 / 5 = 4 units
    expected_size = 4.0
    
    print(f"Equity: ${equity}")
    print(f"Entry: ${entry_price}, SL: ${stop_loss_price}")
    print(f"Risk per trade: {config.default_risk_per_trade * 100}%")
    print(f"Calculated position size: {position_size:.4f} units")
    print(f"Expected: {expected_size:.4f} units")
    
    assert abs(position_size - expected_size) < 0.0001, f"Position size mismatch: {position_size} != {expected_size}"
    print("✓ PASSED")


def test_stop_loss_close_to_entry():
    """Test behavior when stop-loss is very close to entry."""
    print("\n=== Test: Stop-Loss Close to Entry ===")
    
    config = RiskConfig(default_risk_per_trade=0.01, min_position_size_usd=10.0)
    engine = RiskEngine(config)
    
    # Very tight SL (0.1% distance)
    equity = 1000.0
    entry_price = 100.0
    stop_loss_price = 99.90  # 0.1% SL
    
    position_size = engine.compute_position_size(equity, entry_price, stop_loss_price)
    
    # Expected: (1000 * 0.01) / (100 - 99.90) = 10 / 0.10 = 100 units
    expected_size = 100.0
    
    print(f"Equity: ${equity}")
    print(f"Entry: ${entry_price}, SL: ${stop_loss_price} (tight SL)")
    print(f"SL distance: ${entry_price - stop_loss_price:.2f}")
    print(f"Calculated position size: {position_size:.4f} units")
    print(f"Expected: {expected_size:.4f} units")
    
    assert abs(position_size - expected_size) < 0.0001, f"Position size mismatch: {position_size} != {expected_size}"
    print("✓ PASSED")


def test_invalid_inputs():
    """Test handling of invalid inputs."""
    print("\n=== Test: Invalid Input Handling ===")
    
    config = RiskConfig()
    engine = RiskEngine(config)
    
    # Test 1: Invalid ATR (should raise ValueError)
    print("Test 1: Invalid ATR")
    try:
        order = engine.apply_risk_to_signal(
            signal="LONG",
            equity=1000.0,
            entry_price=100.0,
            atr=0.0  # Invalid ATR
        )
        print("✗ FAILED - Should have raised ValueError")
        assert False
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
    
    # Test 2: Zero equity
    print("\nTest 2: Zero equity")
    try:
        engine.compute_position_size(0.0, 100.0, 95.0)
        print("✗ FAILED - Should have raised ValueError")
        assert False
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
    
    # Test 3: Negative entry price
    print("\nTest 3: Negative entry price")
    try:
        engine.compute_position_size(1000.0, -100.0, 95.0)
        print("✗ FAILED - Should have raised ValueError")
        assert False
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
    
    # Test 4: SL equals entry
    print("\nTest 4: SL equals entry")
    try:
        engine.compute_position_size(1000.0, 100.0, 100.0)
        print("✗ FAILED - Should have raised ValueError")
        assert False
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
    
    # Test 5: Invalid risk fraction
    print("\nTest 5: Invalid risk fraction (> 1.0)")
    try:
        engine.compute_position_size(1000.0, 100.0, 95.0, risk_per_trade=1.5)
        print("✗ FAILED - Should have raised ValueError")
        assert False
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
    
    print("\n✓ ALL INVALID INPUT TESTS PASSED")


def test_risk_per_trade_respected():
    """Test that risk_per_trade is properly respected."""
    print("\n=== Test: Risk Per Trade Respected ===")
    
    config = RiskConfig(default_risk_per_trade=0.01)
    engine = RiskEngine(config)
    
    equity = 5000.0
    entry_price = 50.0
    stop_loss_price = 48.0  # $2 SL distance
    
    # Test with default risk (1%)
    position_size = engine.compute_position_size(equity, entry_price, stop_loss_price)
    risk_usd = position_size * (entry_price - stop_loss_price)
    expected_risk = equity * 0.01  # 1% of $5000 = $50
    
    print(f"Equity: ${equity}")
    print(f"Entry: ${entry_price}, SL: ${stop_loss_price}")
    print(f"Position size: {position_size:.4f} units")
    print(f"Risk in USD: ${risk_usd:.2f}")
    print(f"Expected risk: ${expected_risk:.2f}")
    
    assert abs(risk_usd - expected_risk) < 0.01, f"Risk mismatch: {risk_usd} != {expected_risk}"
    
    # Test with custom risk (2%)
    position_size_2pct = engine.compute_position_size(equity, entry_price, stop_loss_price, risk_per_trade=0.02)
    risk_usd_2pct = position_size_2pct * (entry_price - stop_loss_price)
    expected_risk_2pct = equity * 0.02  # 2% of $5000 = $100
    
    print(f"\nWith 2% risk:")
    print(f"Position size: {position_size_2pct:.4f} units")
    print(f"Risk in USD: ${risk_usd_2pct:.2f}")
    print(f"Expected risk: ${expected_risk_2pct:.2f}")
    
    assert abs(risk_usd_2pct - expected_risk_2pct) < 0.01, f"Risk mismatch: {risk_usd_2pct} != {expected_risk_2pct}"
    print("\n✓ PASSED")


def test_atr_based_sl_tp():
    """Test ATR-based stop-loss and take-profit calculation."""
    print("\n=== Test: ATR-Based SL/TP Calculation ===")
    
    config = RiskConfig(default_sl_atr_mult=2.0, default_tp_atr_mult=4.0)
    engine = RiskEngine(config)
    
    entry_price = 100.0
    atr = 2.5
    
    # Test LONG position
    sl, tp = engine.compute_sl_tp_from_atr(entry_price, atr, "LONG")
    
    expected_sl = entry_price - (atr * 2.0)  # 100 - (2.5 * 2) = 95
    expected_tp = entry_price + (atr * 4.0)  # 100 + (2.5 * 4) = 110
    
    print(f"Entry: ${entry_price}, ATR: ${atr}")
    print(f"Signal: LONG")
    print(f"Calculated SL: ${sl:.2f}, TP: ${tp:.2f}")
    print(f"Expected SL: ${expected_sl:.2f}, TP: ${expected_tp:.2f}")
    
    assert abs(sl - expected_sl) < 0.01, f"SL mismatch: {sl} != {expected_sl}"
    assert abs(tp - expected_tp) < 0.01, f"TP mismatch: {tp} != {expected_tp}"
    print("✓ PASSED")


def test_apply_risk_to_signal_long():
    """Test complete risk application to a LONG signal."""
    print("\n=== Test: Apply Risk to LONG Signal ===")
    
    config = RiskConfig(
        default_risk_per_trade=0.02,
        default_sl_atr_mult=1.5,
        default_tp_atr_mult=3.0,
        min_position_size_usd=10.0
    )
    engine = RiskEngine(config)
    
    equity = 1000.0
    entry_price = 100.0
    atr = 5.0
    
    order = engine.apply_risk_to_signal(
        signal="LONG",
        equity=equity,
        entry_price=entry_price,
        atr=atr
    )
    
    assert order is not None, "Order should not be None"
    
    print(f"Equity: ${equity}")
    print(f"Entry: ${entry_price}, ATR: ${atr}")
    print(f"\nOrder details:")
    print(f"  Signal: {order['signal']}")
    print(f"  Side: {order['side']}")
    print(f"  Position size: {order['position_size']:.6f} units")
    print(f"  Position value: ${order['position_value_usd']:.2f}")
    print(f"  Entry: ${order['entry_price']:.2f}")
    print(f"  Stop-loss: ${order['stop_loss']:.2f}")
    print(f"  Take-profit: ${order['take_profit']:.2f}")
    print(f"  Risk (USD): ${order['risk_usd']:.2f}")
    
    # Verify risk is approximately 2% of equity
    expected_risk = equity * 0.02
    assert abs(order['risk_usd'] - expected_risk) < 0.01, f"Risk mismatch: {order['risk_usd']} != {expected_risk}"
    
    # Verify SL/TP are calculated correctly
    expected_sl = entry_price - (atr * 1.5)
    expected_tp = entry_price + (atr * 3.0)
    assert abs(order['stop_loss'] - expected_sl) < 0.01, f"SL mismatch: {order['stop_loss']} != {expected_sl}"
    assert abs(order['take_profit'] - expected_tp) < 0.01, f"TP mismatch: {order['take_profit']} != {expected_tp}"
    
    print("\n✓ PASSED")


def test_min_position_size_rejection():
    """Test that trades below minimum position size are rejected."""
    print("\n=== Test: Minimum Position Size Rejection ===")
    
    config = RiskConfig(
        default_risk_per_trade=0.001,  # Very small risk
        min_position_size_usd=100.0  # High minimum
    )
    engine = RiskEngine(config)
    
    equity = 1000.0
    entry_price = 100.0
    atr = 5.0
    
    order = engine.apply_risk_to_signal(
        signal="LONG",
        equity=equity,
        entry_price=entry_price,
        atr=atr
    )
    
    print(f"Equity: ${equity}, Risk: {config.default_risk_per_trade * 100}%")
    print(f"Minimum position size: ${config.min_position_size_usd}")
    print(f"Order result: {order}")
    
    assert order is None, "Order should be None due to minimum position size"
    print("✓ PASSED - Trade correctly rejected")


def test_max_exposure_capping():
    """Test that max exposure caps position size."""
    print("\n=== Test: Max Exposure Capping ===")
    
    config = RiskConfig(
        default_risk_per_trade=0.10,  # 10% risk (very high)
        max_exposure=0.05,  # But cap at 5% exposure
        min_position_size_usd=1.0
    )
    engine = RiskEngine(config)
    
    equity = 1000.0
    entry_price = 100.0
    atr = 1.0  # Small ATR to create large position
    
    order = engine.apply_risk_to_signal(
        signal="LONG",
        equity=equity,
        entry_price=entry_price,
        atr=atr
    )
    
    assert order is not None, "Order should not be None"
    
    max_position_value = equity * config.max_exposure
    
    print(f"Equity: ${equity}")
    print(f"Max exposure: {config.max_exposure * 100}%")
    print(f"Max position value: ${max_position_value:.2f}")
    print(f"Actual position value: ${order['position_value_usd']:.2f}")
    
    # Position should be capped at max exposure
    assert order['position_value_usd'] <= max_position_value + 0.01, \
        f"Position exceeds max exposure: {order['position_value_usd']} > {max_position_value}"
    
    print("✓ PASSED - Position correctly capped")


def test_flat_signal():
    """Test that FLAT signal returns None."""
    print("\n=== Test: FLAT Signal ===")
    
    config = RiskConfig()
    engine = RiskEngine(config)
    
    order = engine.apply_risk_to_signal(
        signal="FLAT",
        equity=1000.0,
        entry_price=100.0,
        atr=5.0
    )
    
    print(f"Signal: FLAT")
    print(f"Order result: {order}")
    
    assert order is None, "FLAT signal should return None"
    print("✓ PASSED")


def run_all_tests():
    """Run all risk engine tests."""
    print("\n" + "="*60)
    print("RISK ENGINE TEST SUITE")
    print("="*60)
    
    tests = [
        test_position_size_calculation,
        test_stop_loss_close_to_entry,
        test_invalid_inputs,
        test_risk_per_trade_respected,
        test_atr_based_sl_tp,
        test_apply_risk_to_signal_long,
        test_min_position_size_rejection,
        test_max_exposure_capping,
        test_flat_signal,
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
            failed += 1
    
    print("\n" + "="*60)
    print(f"TEST RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
