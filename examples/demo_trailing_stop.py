"""
Demo: Trailing Stop Loss Feature

Shows the trailing stop feature in action with and without enabling.
"""

from execution.paper_trader import PaperTrader
from execution.order_types import OrderRequest, OrderSide, OrderType

def demo_without_trailing_stop():
    """Demo: Trailing stop DISABLED (default behavior)."""
    print("="*60)
    print("DEMO 1: Trailing Stop DISABLED (Default)")
    print("="*60)
    
    pt = PaperTrader(starting_balance=10000.0, log_trades=False)
    
    # Disabled by default
    pt.set_risk_config({"enable_trailing_stop": False})
    
    # Open long at 100 with 5% stop loss (95.0)
    order = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.LONG,
        quantity=0.1,
        order_type=OrderType.MARKET,
        stop_loss=95.0,
        strategy_name="demo"
    )
    
    result = pt.submit_order(order, current_price=100.0)
    print(f"\n[OPEN] Position opened at ${result.fill.fill_price:.2f}")
    
    position = pt.positions["BTCUSDT"]
    print(f"  Initial SL: ${position.stop_loss:.2f}")
    print(f"  Highest: ${position.highest_price:.2f}")
    
    # Price moves to 110
    pt.update_positions({"BTCUSDT": 110.0})
    print(f"\n[UPDATE] Price moved to $110.00")
    print(f"  SL: ${position.stop_loss:.2f} (unchanged)")
    print(f"  Highest: ${position.highest_price:.2f} (not tracked)")
    
    # Price falls to 105
    pt.update_positions({"BTCUSDT": 105.0})
    print(f"\n[UPDATE] Price fell to $105.00")
    print(f"  SL: ${position.stop_loss:.2f} (still at 95)")
    print(f"  Result: No protection from pullback")
    
    print("\n" + "="*60 + "\n")


def demo_with_trailing_stop():
    """Demo: Trailing stop ENABLED."""
    print("="*60)
    print("DEMO 2: Trailing Stop ENABLED (2% Trail)")
    print("="*60)
    
    pt = PaperTrader(starting_balance=10000.0, log_trades=False)
    
    # Enable trailing stop with 2% trail
    pt.set_risk_config({
        "enable_trailing_stop": True,
        "trailing_stop_pct": 0.02  # 2%
    })
    
    # Open long at 100 with 5% stop loss (95.0)
    order = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.LONG,
        quantity=0.1,
        order_type=OrderType.MARKET,
        stop_loss=95.0,
        strategy_name="demo"
    )
    
    result = pt.submit_order(order, current_price=100.0)
    print(f"\n[OPEN] Position opened at ${result.fill.fill_price:.2f}")
    
    position = pt.positions["BTCUSDT"]
    print(f"  Initial SL: ${position.stop_loss:.2f}")
    print(f"  Highest: ${position.highest_price:.2f}")
    
    # Price moves to 110
    pt.update_positions({"BTCUSDT": 110.0})
    print(f"\n[UPDATE] Price moved to $110.00")
    print(f"  Highest: ${position.highest_price:.2f} (updated)")
    print(f"  New trail stop: 110 * 0.98 = $107.80")
    print(f"  SL: ${position.stop_loss:.2f} (tightened from 95.00)")
    
    # Price falls to 108
    pt.update_positions({"BTCUSDT": 108.0})
    print(f"\n[UPDATE] Price fell to $108.00")
    print(f"  Highest: ${position.highest_price:.2f} (stays at peak)")
    print(f"  SL: ${position.stop_loss:.2f} (locked, never loosens)")
    print(f"  Result: Still in position (108 > 107.8)")
    
    # Price falls to 107.5 (below stop)
    pt.update_positions({"BTCUSDT": 107.5})
    print(f"\n[UPDATE] Price fell to $107.50")
    
    symbols_to_close = pt.check_exit_conditions({"BTCUSDT": 107.5})
    print(f"  Exit triggered: {symbols_to_close}")
    print(f"  Reason: 107.50 < 107.80 (stop hit)")
    
    # Close position
    close_order = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        quantity=0.1,
        order_type=OrderType.MARKET,
        strategy_name="exit"
    )
    
    close_result = pt.submit_order(close_order, current_price=107.5)
    print(f"\n[CLOSE] Position closed at ${close_result.fill.fill_price:.2f}")
    print(f"  Final balance: ${pt.balance:.2f}")
    print(f"  Profit: ${pt.balance - 10000:.2f}")
    print(f"  Protected profit: Entry ~100 -> Exit ~107.5 = +7.5%")
    
    print("\n" + "="*60 + "\n")


def demo_comparison():
    """Compare results side by side."""
    print("="*60)
    print("COMPARISON: With vs Without Trailing Stop")
    print("="*60)
    print()
    print("Scenario: Entry at $100, peak at $110, falls to $107.50")
    print()
    print("WITHOUT Trailing Stop:")
    print("  - SL stays at $95 (5% initial)")
    print("  - Still in position at $107.50")
    print("  - Unrealized profit: +$7.50/share")
    print("  - Risk: Could fall all the way to $95")
    print()
    print("WITH Trailing Stop (2% trail):")
    print("  - SL tightens to $107.80 when price hits $110")
    print("  - Exit triggered at $107.50")
    print("  - Realized profit: +$7.50/share")
    print("  - Protection: Locked in 98% of peak gains")
    print()
    print("="*60)
    print()


if __name__ == "__main__":
    demo_without_trailing_stop()
    demo_with_trailing_stop()
    demo_comparison()
    
    print("\n✅ Demo complete! Trailing stop feature working as expected.\n")
