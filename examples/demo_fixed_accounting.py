#!/usr/bin/env python3
"""Demo script showing fixed accounting with INIT logging."""
from execution.paper_trader import PaperTrader
from execution.order_types import OrderRequest, OrderSide, OrderType
from pathlib import Path

# Create a new paper trader with session logging
trader = PaperTrader(
    starting_balance=1000.0,
    commission_rate=0.0005,
    slippage=0.0005,
    log_trades=True,
    log_file=Path("logs/paper_trades/demo_fixed_session.csv")
)

# Simulate some trades
trades = [
    ("BTCUSDT", OrderSide.LONG, 0.01, 50000.0, 50500.0),   # +$5 profit
    ("ETHUSDT", OrderSide.LONG, 0.1, 3000.0, 3050.0),      # +$5 profit
    ("SOLUSDT", OrderSide.SHORT, 10.0, 100.0, 95.0),       # +$50 profit
]

for symbol, side, qty, entry_price, exit_price in trades:
    # Open position
    open_order = OrderRequest(
        symbol=symbol,
        side=side,
        order_type=OrderType.MARKET,
        quantity=qty
    )
    trader.submit_order(open_order, entry_price)
    
    # Close position
    close_side = OrderSide.SHORT if side == OrderSide.LONG else OrderSide.LONG
    close_order = OrderRequest(
        symbol=symbol,
        side=close_side,
        order_type=OrderType.MARKET,
        quantity=qty
    )
    trader.submit_order(close_order, exit_price)

print(f"\nDemo session created: {trader.log_file}")
print(f"Starting balance: ${trader.starting_balance:.2f}")
print(f"Final balance: ${trader.balance:.2f}")
print(f"Actual profit: ${trader.balance - trader.starting_balance:.2f}")
