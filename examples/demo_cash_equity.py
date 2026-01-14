"""
Cash+Equity Model Demo

Demonstrates the refactored accounting:
- Balance (cash) unchanged on OPEN
- Balance changes ONLY on CLOSE
- Equity = balance + unrealized PnL
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from execution import PaperTrader, OrderRequest, OrderSide, OrderType


def main():
    print("="*60)
    print("CASH+EQUITY ACCOUNTING MODEL DEMO")
    print("="*60)
    
    trader = PaperTrader(
        starting_balance=10000.0,
        slippage=0.001,
        commission_rate=0.001,
        log_trades=False
    )
    
    print(f"\nStarting balance: ${trader.get_balance():.2f}")
    print(f"Starting equity:  ${trader.get_equity():.2f}")
    
    print("\n" + "="*60)
    print("STEP 1: Open LONG position at $50,000")
    print("="*60)
    
    order1 = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.LONG,
        order_type=OrderType.MARKET,
        quantity=0.1
    )
    trader.submit_order(order1, current_price=50000.0)
    
    print(f"Balance AFTER OPEN: ${trader.get_balance():.2f} (UNCHANGED!)")
    print(f"Equity AFTER OPEN:  ${trader.get_equity():.2f}")
    print(f"Open positions: {len(trader.get_open_positions())}")
    
    print("\n" + "="*60)
    print("STEP 2: Price moves to $52,000 (profit)")
    print("="*60)
    
    trader.update_positions({"BTCUSDT": 52000.0})
    
    positions = trader.get_open_positions()
    unrealized = positions["BTCUSDT"].unrealized_pnl
    
    print(f"Balance: ${trader.get_balance():.2f} (STILL unchanged)")
    print(f"Unrealized PnL: ${unrealized:.2f}")
    print(f"Equity: ${trader.get_equity():.2f} (balance + unrealized)")
    
    print("\n" + "="*60)
    print("STEP 3: Close position at $52,000")
    print("="*60)
    
    close_order = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.1
    )
    trader.submit_order(close_order, current_price=52000.0)
    
    print(f"Balance AFTER CLOSE: ${trader.get_balance():.2f} (NOW changed!)")
    print(f"Equity AFTER CLOSE:  ${trader.get_equity():.2f}")
    print(f"Realized PnL: ${trader.realized_pnl:.2f}")
    print(f"Open positions: {len(trader.get_open_positions())}")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    perf = trader.get_performance_summary()
    print(f"\nStarting balance:  ${perf['starting_balance']:.2f}")
    print(f"Final balance:     ${perf['current_balance']:.2f}")
    print(f"Final equity:      ${perf['equity']:.2f}")
    print(f"Realized PnL:      ${perf['realized_pnl']:.2f}")
    print(f"Total trades:      {perf['total_trades']}")
    
    profit = perf['current_balance'] - perf['starting_balance']
    print(f"\nNet profit: ${profit:.2f} ({profit/perf['starting_balance']*100:.2f}%)")
    
    print("\n" + "="*60)
    print("KEY POINTS:")
    print("="*60)
    print("1. Balance did NOT change when opening position")
    print("2. Balance ONLY changed when closing position")
    print("3. Equity tracked unrealized PnL during open position")
    print("4. After close, equity = balance (no open positions)")
    print("="*60)


if __name__ == "__main__":
    main()
