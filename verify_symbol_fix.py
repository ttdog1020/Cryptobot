"""
Symbol Propagation Fix Verification

This script verifies that the symbol propagation fixes are in place
and working correctly.
"""

import sys
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

from execution import ExecutionEngine, PaperTrader, OrderRequest, OrderSide, OrderType


def test_unknown_symbol_rejection():
    """Test that UNKNOWN symbols are rejected."""
    print("=" * 60)
    print("SYMBOL PROPAGATION FIX VERIFICATION")
    print("=" * 60)
    
    engine = ExecutionEngine(
        execution_mode="paper",
        paper_trader=PaperTrader(starting_balance=10000.0, log_trades=False)
    )
    
    # Test 1: UNKNOWN symbol
    print("\n✓ Test 1: UNKNOWN symbol rejection")
    try:
        order = OrderRequest(
            symbol="UNKNOWN",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        engine.submit_order(order, current_price=50000.0)
        print("  ✗ FAILED - Order with UNKNOWN symbol was accepted!")
        return False
    except ValueError as e:
        if "Invalid symbol" in str(e) and "UNKNOWN" in str(e):
            print(f"  ✓ PASSED - Correctly rejected with: {e}")
        else:
            print(f"  ✗ FAILED - Wrong error message: {e}")
            return False
    
    # Test 2: Empty symbol
    print("\n✓ Test 2: Empty symbol rejection")
    try:
        order = OrderRequest(
            symbol="",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        engine.submit_order(order, current_price=50000.0)
        print("  ✗ FAILED - Order with empty symbol was accepted!")
        return False
    except ValueError as e:
        if "Invalid symbol" in str(e):
            print(f"  ✓ PASSED - Correctly rejected with: {e}")
        else:
            print(f"  ✗ FAILED - Wrong error message: {e}")
            return False
    
    # Test 3: Valid symbol
    print("\n✓ Test 3: Valid symbol acceptance")
    try:
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.LONG,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        result = engine.submit_order(order, current_price=50000.0)
        if result.success:
            print(f"  ✓ PASSED - Valid symbol BTCUSDT accepted")
        else:
            print(f"  ✗ FAILED - Valid symbol rejected: {result.error}")
            return False
    except Exception as e:
        print(f"  ✗ FAILED - Unexpected error: {e}")
        return False
    
    # Test 4: create_order_from_risk_output without symbol
    print("\n✓ Test 4: Risk output missing symbol rejection")
    try:
        risk_output = {
            "side": "LONG",
            "entry_price": 50000.0,
            "position_size": 0.1,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
            # Missing 'symbol' key
        }
        engine.create_order_from_risk_output(risk_output)
        print("  ✗ FAILED - Risk output without symbol was accepted!")
        return False
    except ValueError as e:
        if "missing valid symbol" in str(e):
            print(f"  ✓ PASSED - Correctly rejected with: {e}")
        else:
            print(f"  ✗ FAILED - Wrong error message: {e}")
            return False
    
    # Test 5: create_order_from_risk_output with UNKNOWN symbol
    print("\n✓ Test 5: Risk output with UNKNOWN symbol rejection")
    try:
        risk_output = {
            "symbol": "UNKNOWN",
            "side": "LONG",
            "entry_price": 50000.0,
            "position_size": 0.1,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
        }
        engine.create_order_from_risk_output(risk_output)
        print("  ✗ FAILED - Risk output with UNKNOWN symbol was accepted!")
        return False
    except ValueError as e:
        if "missing valid symbol" in str(e):
            print(f"  ✓ PASSED - Correctly rejected with: {e}")
        else:
            print(f"  ✗ FAILED - Wrong error message: {e}")
            return False
    
    # Test 6: create_order_from_risk_output with valid symbol
    print("\n✓ Test 6: Risk output with valid symbol acceptance")
    try:
        risk_output = {
            "symbol": "ETHUSDT",
            "side": "SHORT",
            "entry_price": 3000.0,
            "position_size": 1.0,
            "stop_loss": 3100.0,
            "take_profit": 2900.0,
        }
        order = engine.create_order_from_risk_output(risk_output)
        if order.symbol == "ETHUSDT":
            print(f"  ✓ PASSED - Valid symbol ETHUSDT accepted and propagated")
        else:
            print(f"  ✗ FAILED - Symbol changed to {order.symbol}")
            return False
    except Exception as e:
        print(f"  ✗ FAILED - Unexpected error: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL CHECKS PASSED - Symbol propagation fix verified!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_unknown_symbol_rejection()
    sys.exit(0 if success else 1)
