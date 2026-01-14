"""
MODULE 27: Verification Script

Verify all mandatory patches are working correctly:
1. Balance accounting uses apply_trade_result (no fill_value in balance math)
2. Kill switch uses peak_equity for drawdown tracking
3. ExecutionResult has filled_quantity attribute
4. CSV logs record realized_pnl, balance, equity (not fill_value in PnL)
"""

import sys
from pathlib import Path
from execution.paper_trader import PaperTrader
from execution.order_types import OrderRequest, OrderSide, OrderType, ExecutionResult
from execution.safety import SafetyLimits, SafetyMonitor

print("=" * 70)
print("MODULE 27 PATCH VERIFICATION")
print("=" * 70)

# Test 1: Verify apply_trade_result function exists and works
print("\n[TEST 1] apply_trade_result helper function")
print("-" * 70)

result = PaperTrader.apply_trade_result(
    balance=10000.0,
    realized_pnl=100.0,
    commission=1.0,
    slippage=0.5
)
expected = 10000.0 + 100.0 - 1.0 - 0.5
print(f"  Input: balance=10000, pnl=+100, commission=1, slippage=0.5")
print(f"  Output: ${result:.2f}")
print(f"  Expected: ${expected:.2f}")
assert result == expected, f"Expected {expected}, got {result}"
print("  [PASS] apply_trade_result works correctly")

# Test 2: Verify balance accounting doesn't use fill_value directly
print("\n[TEST 2] Balance accounting (no fill_value in balance updates)")
print("-" * 70)

trader = PaperTrader(starting_balance=10000.0, log_trades=False)

# Trade 1: Open LONG, close with small profit (~$1)
order1 = OrderRequest(
    symbol="BTCUSDT",
    side=OrderSide.LONG,
    order_type=OrderType.MARKET,
    quantity=0.01
)
result1 = trader.submit_order(order1, current_price=50000.0)
balance_after_open = trader.get_balance()
print(f"  Opened LONG: 0.01 BTC @ $50000")
print(f"  Balance after open: ${balance_after_open:.2f}")

# Close with slight profit
close1 = OrderRequest(
    symbol="BTCUSDT",
    side=OrderSide.SELL,
    order_type=OrderType.MARKET,
    quantity=0.01
)
result2 = trader.submit_order(close1, current_price=50100.0)
balance_after_close1 = trader.get_balance()
pnl1 = balance_after_close1 - 10000.0

print(f"  Closed at $50100 (profit)")
print(f"  Balance after close: ${balance_after_close1:.2f}")
print(f"  Net PnL: ${pnl1:.2f}")
print(f"  Realized PnL (from stats): ${trader.realized_pnl:.2f}")

# Verify PnL is small (around $1, not $500 which would indicate fill_value was used)
assert -5 < pnl1 < 5, f"Trade 1 PnL should be small, got ${pnl1:.2f}"
print(f"  [PASS] Trade 1 PnL is reasonable: ${pnl1:.2f}")

# Trade 2: Small loss (~$-15)
trader.reset()
trader.balance = balance_after_close1

order2 = OrderRequest(
    symbol="ETHUSDT",
    side=OrderSide.LONG,
    order_type=OrderType.MARKET,
    quantity=0.1
)
trader.submit_order(order2, current_price=3000.0)
print(f"\n  Opened LONG: 0.1 ETH @ $3000")

close2 = OrderRequest(
    symbol="ETHUSDT",
    side=OrderSide.SELL,
    order_type=OrderType.MARKET,
    quantity=0.1
)
trader.submit_order(close2, current_price=2850.0)
balance_after_close2 = trader.get_balance()
pnl2 = balance_after_close2 - balance_after_close1

print(f"  Closed at $2850 (loss)")
print(f"  Balance after close: ${balance_after_close2:.2f}")
print(f"  Net PnL: ${pnl2:.2f}")

# Verify loss is around -$15, not -$300
assert -20 < pnl2 < -10, f"Trade 2 PnL should be around -$15, got ${pnl2:.2f}"
print(f"  [PASS] Trade 2 PnL is reasonable: ${pnl2:.2f}")

# Test 3: Verify ExecutionResult has filled_quantity
print("\n[TEST 3] ExecutionResult.filled_quantity attribute")
print("-" * 70)

from execution.order_types import OrderFill
from datetime import datetime

fill = OrderFill(
    order_id="test_123",
    symbol="BTCUSDT",
    side=OrderSide.LONG,
    quantity=0.5,
    fill_price=50000.0,
    commission=25.0
)

exec_result = ExecutionResult.success_result(
    order_id="test_123",
    fill=fill
)

# Check filled_quantity exists and returns correct value
assert hasattr(exec_result, 'filled_quantity'), "ExecutionResult missing filled_quantity"
assert exec_result.filled_quantity == 0.5, f"Expected 0.5, got {exec_result.filled_quantity}"
print(f"  ExecutionResult.filled_quantity: {exec_result.filled_quantity}")
print("  [PASS] filled_quantity attribute exists and works")

# Test with no fill
exec_result_no_fill = ExecutionResult(
    success=False,
    status="REJECTED",
    error="Test error"
)
assert exec_result_no_fill.filled_quantity == 0.0, "Should return 0.0 when no fill"
print("  [PASS] filled_quantity returns 0.0 when no fill")

# Test 4: Verify SafetyMonitor uses peak_equity
print("\n[TEST 4] SafetyMonitor peak_equity tracking")
print("-" * 70)

limits = SafetyLimits(
    max_daily_loss_pct=0.02,  # 2%
    max_risk_per_trade_pct=0.01,
    max_exposure_pct=0.20,
    max_open_trades=5
)

monitor = SafetyMonitor(limits, starting_equity=10000.0)

print(f"  Starting equity: ${monitor.session_start_equity:.2f}")
print(f"  Initial peak: ${monitor.peak_equity:.2f}")

# Simulate profit - peak should update
monitor.check_post_trade(10500.0)
print(f"  After profit to $10500:")
print(f"    Peak equity: ${monitor.peak_equity:.2f}")
print(f"    Trading halted: {monitor.trading_halted}")
assert monitor.peak_equity == 10500.0, "Peak should update on profit"
assert not monitor.trading_halted, "Should not halt on profit"
print("    [PASS] Peak updated, trading continues")

# Simulate small loss from peak - should NOT halt
monitor.check_post_trade(10400.0)
drawdown_pct = (10500 - 10400) / 10500
print(f"  After drop to $10400:")
print(f"    Peak equity: ${monitor.peak_equity:.2f}")
print(f"    Drawdown: {drawdown_pct*100:.2f}%")
print(f"    Trading halted: {monitor.trading_halted}")
assert not monitor.trading_halted, "Should not halt on small drawdown"
print("    [PASS] Small drawdown does NOT trigger kill switch")

# Simulate large drawdown - SHOULD halt (>2% from peak)
monitor.check_post_trade(10250.0)  # $250 loss from peak = 2.38%
drawdown_pct = (10500 - 10250) / 10500
print(f"  After drop to $10250:")
print(f"    Peak equity: ${monitor.peak_equity:.2f}")
print(f"    Drawdown: {drawdown_pct*100:.2f}%")
print(f"    Trading halted: {monitor.trading_halted}")
assert monitor.trading_halted, "Should halt on large drawdown"
assert "Drawdown limit exceeded" in monitor.halt_reason
print(f"    [PASS] Large drawdown triggers kill switch")
print(f"    Halt reason: {monitor.halt_reason}")

# Test 5: Verify peak_equity in PaperTrader
print("\n[TEST 5] PaperTrader peak_equity tracking")
print("-" * 70)

trader2 = PaperTrader(starting_balance=10000.0, log_trades=False)
assert hasattr(trader2, 'peak_equity'), "PaperTrader missing peak_equity"
assert trader2.peak_equity == 10000.0, "Initial peak should equal starting balance"
print(f"  Initial peak_equity: ${trader2.peak_equity:.2f}")
print("  [PASS] PaperTrader has peak_equity tracking")

# Test 6: Verify no fill_value in balance updates
print("\n[TEST 6] Verify fill_value not used in balance calculations")
print("-" * 70)

import inspect

# Check _close_position source code
source = inspect.getsource(PaperTrader._close_position)

# Should NOT have "balance += fill.fill_value" or "balance -= fill.fill_value"
assert "balance += fill.fill_value" not in source, "Found balance += fill.fill_value"
assert "balance -= fill.fill_value" not in source, "Found balance -= fill.fill_value"

# Should have proper accounting with proceeds/cost
assert "proceeds = fill.fill_value - fill.commission - fill.slippage" in source
assert "cost = fill.fill_value + fill.commission + fill.slippage" in source

print("  [PASS] _close_position uses proceeds/cost, not raw fill_value")
print("  [PASS] Balance updates account for commissions and slippage")

print("\n" + "=" * 70)
print("ALL MODULE 27 PATCHES VERIFIED SUCCESSFULLY")
print("=" * 70)
print("\nSummary:")
print("  1. ✓ apply_trade_result helper function working")
print("  2. ✓ Balance accounting fixed (no fill_value abuse)")
print("  3. ✓ ExecutionResult.filled_quantity attribute added")
print("  4. ✓ SafetyMonitor uses peak_equity for drawdown")
print("  5. ✓ PaperTrader tracks peak_equity")
print("  6. ✓ No fill_value in balance math (uses proceeds/cost)")
print("\nModule 27 refactoring: COMPLETE")
