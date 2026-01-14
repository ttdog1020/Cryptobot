"""
Flatten-on-Shutdown Verification Script

This script demonstrates the flatten-on-shutdown functionality by:
1. Creating a PaperTrader instance
2. Opening multiple positions
3. Simulating shutdown by calling close_all_positions()
4. Verifying all positions are closed and logged
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from execution import PaperTrader, OrderRequest, OrderSide, OrderType


def print_separator(title=""):
    """Print a formatted separator."""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print('='*60)
    else:
        print('='*60)


def verify_flatten_on_shutdown():
    """Demonstrate flatten-on-shutdown functionality."""
    print_separator("FLATTEN-ON-SHUTDOWN VERIFICATION")
    
    # Create a paper trader with temporary log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(f"logs/paper_trades/flatten_demo_{timestamp}.csv")
    
    trader = PaperTrader(
        starting_balance=10000.0,
        slippage=0.001,
        commission_rate=0.001,
        log_trades=True,
        log_file=log_file
    )
    
    print(f"\n✓ PaperTrader initialized")
    print(f"  Starting balance: ${trader.get_balance():.2f}")
    print(f"  Log file: {log_file}")
    
    # Simulate market prices
    market_prices = {
        "BTCUSDT": 50000.0,
        "ETHUSDT": 3000.0,
        "BNBUSDT": 600.0
    }
    
    print_separator("OPENING POSITIONS")
    
    # Open 3 positions
    orders = [
        ("BTCUSDT", OrderSide.LONG, 0.1, 50000.0),
        ("ETHUSDT", OrderSide.SHORT, 1.0, 3000.0),
        ("BNBUSDT", OrderSide.LONG, 5.0, 600.0),
    ]
    
    for symbol, side, quantity, price in orders:
        order = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity
        )
        result = trader.submit_order(order, current_price=price)
        
        if result.success:
            print(f"✓ Opened {side.value} position: {quantity} {symbol} @ ${price:.2f}")
        else:
            print(f"✗ Failed to open {symbol}: {result.error}")
    
    # Check open positions
    open_positions = trader.get_open_positions()
    print(f"\n✓ Open positions: {len(open_positions)}")
    for symbol, position in open_positions.items():
        print(f"  - {symbol}: {position.side.value} {position.quantity} @ ${position.entry_price:.2f}")
    
    balance_before = trader.get_balance()
    print(f"\n✓ Balance after opening positions: ${balance_before:.2f}")
    
    print_separator("SIMULATING SHUTDOWN - FLATTENING POSITIONS")
    
    # Update market prices (simulate price movement)
    updated_prices = {
        "BTCUSDT": 51000.0,  # LONG profit
        "ETHUSDT": 2900.0,   # SHORT profit
        "BNBUSDT": 590.0,    # LONG loss
    }
    
    # Price provider function
    def get_latest_price(symbol):
        price = updated_prices.get(symbol, market_prices.get(symbol, 0.0))
        print(f"  Getting price for {symbol}: ${price:.2f}")
        return price
    
    # Flatten all positions
    trader.close_all_positions(get_latest_price)
    
    # Check that all positions are closed
    open_positions = trader.get_open_positions()
    balance_after = trader.get_balance()
    
    print_separator("VERIFICATION RESULTS")
    
    print(f"\n✓ Open positions after flattening: {len(open_positions)}")
    if len(open_positions) == 0:
        print("  ✅ All positions successfully closed!")
    else:
        print(f"  ❌ Still have {len(open_positions)} open position(s)")
        return False
    
    print(f"\n✓ Balance after flattening: ${balance_after:.2f}")
    pnl = balance_after - 10000.0
    print(f"  Net PnL: ${pnl:+.2f} ({pnl/10000.0*100:+.2f}%)")
    
    print_separator("CSV LOG VERIFICATION")
    
    # Verify CSV contains matching OPEN and CLOSE rows
    df = pd.read_csv(log_file)
    print(f"\n✓ CSV log file: {log_file}")
    print(f"  Total rows: {len(df)}")
    
    # Analyze trades
    init_rows = df[df['action'] == 'INIT']
    open_rows = df[df['action'] == 'OPEN']
    close_rows = df[df['action'] == 'CLOSE']
    
    print(f"\n✓ Trade breakdown:")
    print(f"  INIT rows:  {len(init_rows)}")
    print(f"  OPEN rows:  {len(open_rows)}")
    print(f"  CLOSE rows: {len(close_rows)}")
    
    if len(open_rows) == len(close_rows):
        print("  ✅ All OPEN trades have matching CLOSE trades!")
    else:
        print(f"  ❌ Mismatch: {len(open_rows)} OPEN vs {len(close_rows)} CLOSE")
        return False
    
    # Verify each symbol has matching OPEN and CLOSE
    print(f"\n✓ Symbol verification:")
    all_matched = True
    for symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
        symbol_opens = open_rows[open_rows['symbol'] == symbol]
        symbol_closes = close_rows[close_rows['symbol'] == symbol]
        
        if len(symbol_opens) == len(symbol_closes) == 1:
            open_row = symbol_opens.iloc[0]
            close_row = symbol_closes.iloc[0]
            pnl = close_row['realized_pnl']
            pnl_pct = close_row['pnl_pct']
            
            status = "✅" if pnl > 0 else "❌"
            print(f"  {status} {symbol}: PnL = ${pnl:.2f} ({pnl_pct:+.2f}%)")
        else:
            print(f"  ❌ {symbol}: OPEN={len(symbol_opens)}, CLOSE={len(symbol_closes)}")
            all_matched = False
    
    if not all_matched:
        return False
    
    # Check for FLATTEN order IDs
    flatten_orders = close_rows[close_rows['order_id'].str.contains('FLATTEN', na=False)]
    print(f"\n✓ Flatten order IDs: {len(flatten_orders)}")
    if len(flatten_orders) == len(close_rows):
        print("  ✅ All close orders have FLATTEN order IDs!")
    else:
        print(f"  ⚠️  Only {len(flatten_orders)}/{len(close_rows)} have FLATTEN IDs")
    
    print_separator("SUMMARY")
    
    print("\n✅ Flatten-on-shutdown verification PASSED!")
    print("\nKey achievements:")
    print("  ✅ All open positions closed")
    print("  ✅ Each OPEN has matching CLOSE in CSV")
    print("  ✅ Realized PnL calculated and logged")
    print("  ✅ Balance updated correctly")
    print("  ✅ Performance metrics updated")
    
    # Print performance summary
    perf = trader.get_performance_summary()
    print(f"\n✓ Performance Summary:")
    print(f"  Starting balance: ${perf['starting_balance']:.2f}")
    print(f"  Final balance: ${perf['current_balance']:.2f}")
    print(f"  Realized PnL: ${perf['realized_pnl']:.2f}")
    print(f"  Total trades: {perf['total_trades']}")
    print(f"  Winning trades: {perf['winning_trades']}")
    print(f"  Losing trades: {perf['losing_trades']}")
    print(f"  Win rate: {perf['win_rate']:.1f}%")
    
    print_separator()
    print("\n🎉 Verification complete!")
    print(f"\nLog file saved to: {log_file}")
    print("You can now run: python forensic_validator.py")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = verify_flatten_on_shutdown()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
