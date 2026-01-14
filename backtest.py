import argparse
import os
from datetime import datetime, timezone

import math
import pandas as pd

from bot import BotConfig, PaperTrader, create_exchange, fetch_ohlcv, _apply_indicators_with_profile, _generate_signal_with_profile
from strategy_engine import load_strategy_profile
from fetch_ohlcv_paged import fetch_ohlcv_paged


# Backtest configuration defaults (env-driven)
DEFAULT_SYMBOL = os.getenv("BACKTEST_SYMBOL") or os.getenv("SYMBOL", "ETH/USDT")
DEFAULT_TIMEFRAME = os.getenv("BACKTEST_TIMEFRAME") or os.getenv("TIMEFRAME", "15m")
DEFAULT_LIMIT = int(os.getenv("BACKTEST_LIMIT", "20000"))
DEFAULT_MULTI_SYMBOL = os.getenv("MULTI_SYMBOL", "0") == "1"
DEFAULT_EXCHANGE = os.getenv("BACKTEST_EXCHANGE") or os.getenv("EXCHANGE")


def run_backtest(symbol: str | None = None, timeframe: str | None = None, limit: int | None = None, exchange_override: str | None = None):
    """
    Run a single-symbol backtest using provided overrides or environment defaults.
    Args:
        symbol: Trading pair to backtest (e.g., \"ETH/USDT\").
        timeframe: Candle timeframe (e.g., \"15m\").
        limit: Number of candles to fetch.
        exchange_override: Optional exchange name to override BotConfig.exchange_name.
    """
    config = BotConfig()
    # Allow backtest to override the exchange via env
    backtest_exchange = exchange_override or os.getenv("BACKTEST_EXCHANGE")
    if backtest_exchange:
        config.exchange_name = backtest_exchange.lower()
    symbol = symbol or DEFAULT_SYMBOL
    timeframe = timeframe or DEFAULT_TIMEFRAME
    limit = int(limit or DEFAULT_LIMIT)

    print("=== Backtest starting ===")
    print(f"Symbol: {symbol} | Timeframe: {timeframe} | Candles: {limit}")
    print(f"Starting balance: {config.starting_balance}, risk_per_trade_pct: {config.risk_per_trade_pct}")

    exchange = create_exchange(config)

    # Fetch historical candles via paginated REST
    print(f"Fetching {limit} candles...")
    ohlcv = fetch_ohlcv_paged(exchange, symbol, timeframe, limit)
    if not ohlcv or len(ohlcv) < 50:
        print("[ERROR] Not enough historical candles for backtest.")
        return
    
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    print(f"Fetched {len(df)} candles successfully.")

    # Initialize trader with strategy profile
    profile = load_strategy_profile(symbol, timeframe)
    if profile is not None:
        print(f"[STRATEGY] Loaded profile for {symbol} {timeframe}: {profile}")
    else:
        print(f"[STRATEGY] No profile found for {symbol} {timeframe}; using internal defaults.")
    
    trader = PaperTrader(
        balance=config.starting_balance,
        strategy_profile=profile,
    )

    # Add indicators using profile
    df = _apply_indicators_with_profile(df, trader)

    positions_opened = 0

    # Walk forward bar-by-bar
    for i in range(30, len(df)):
        row = df.iloc[i]
        price = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])

        # Extract ATR for this bar
        atr_val = float(row.get("atr", float("nan")))
        if math.isnan(atr_val):
            atr_val = None

        # MODULE 5: Check ATR-based SL/TP using high/low of bar
        if trader.position_side == "LONG":
            if trader.stop_loss is not None and trader.take_profit is not None:
                # Check if stop-loss was hit (low <= SL)
                if low <= trader.stop_loss:
                    print(f"[RISK] Stop-loss hit at {trader.stop_loss:.2f} (bar low={low:.2f}).")
                    trader.close_position(trader.stop_loss)
                # Check if take-profit was hit (high >= TP)
                elif high >= trader.take_profit:
                    print(f"[RISK] Take-profit hit at {trader.take_profit:.2f} (bar high={high:.2f}).")
                    trader.close_position(trader.take_profit)

        # Prepare window up to current bar for signal generation
        window = df.iloc[: i + 1].copy()
        signal = _generate_signal_with_profile(window, trader)

        if signal == "BUY" and trader.position_side is None:
            trader.open_long(price, atr=atr_val)
            positions_opened += 1
        elif signal == "SELL":
            trader.close_position(price)

        trader.mark_to_market(price)

    # Close any open position at last price
    last_price = float(df.iloc[-1]["close"])
    if trader.position_side == "LONG":
        trader.close_position(last_price)

    # Summarize
    summary = trader.get_summary()
    total_trades = summary["total_trades"]
    total_pnl = summary["total_pnl"]
    final_equity = summary["final_equity"]
    max_equity = summary["max_equity"]
    min_equity = summary["min_equity"]

    wins = sum(1 for pnl in trader.closed_trade_pnls if pnl > 0)
    losses = sum(1 for pnl in trader.closed_trade_pnls if pnl < 0)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

    print("\n=== Backtest Summary ===")
    print(f"Bars tested: {len(df)} (using {len(df) - 30} after warm-up)")
    print(f"Total closed trades: {total_trades}")
    print(f"Wins: {wins}, Losses: {losses}, Win rate: {win_rate:.1f}%")
    print(f"Total PnL: {total_pnl:.4f}")
    print(f"Final equity: {final_equity:.4f}")
    print(f"Max equity: {max_equity:.4f}")
    print(f"Min equity: {min_equity:.4f}")
    print("=== End Backtest ===")
    return summary


def parse_cli_args() -> argparse.Namespace:
    """Parse CLI args for running backtests without relying solely on env vars."""
    parser = argparse.ArgumentParser(description="Run a backtest for a symbol/timeframe.")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help=f"Trading pair to backtest (default: {DEFAULT_SYMBOL}).")
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME, help=f"Candle timeframe (default: {DEFAULT_TIMEFRAME}).")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Number of candles to fetch (default: {DEFAULT_LIMIT}).")
    parser.add_argument("--exchange", default=DEFAULT_EXCHANGE, help="Exchange id to use (overrides BACKTEST_EXCHANGE/EXCHANGE).")
    parser.add_argument("--multi-symbol", dest="multi_symbol", action="store_true", default=DEFAULT_MULTI_SYMBOL, help="Run multi-symbol orchestrator backtest.")
    parser.add_argument("--single", dest="multi_symbol", action="store_false", help="Force single-symbol mode even if MULTI_SYMBOL=1.")
    return parser.parse_args()


if __name__ == "__main__":
    # MODULE 6: Multi-symbol orchestration
    args = parse_cli_args()
    if args.multi_symbol:
        from orchestrator import Orchestrator
        from pathlib import Path
        
        config = BotConfig()
        if args.exchange:
            config.exchange_name = args.exchange.lower()
        exchange = create_exchange(config)
        
        orchestrator = Orchestrator(starting_balance_per_symbol=config.starting_balance)
        symbols = orchestrator.load_symbols(Path("symbols.json"))
        orchestrator.initialize_controllers(exchange, symbols)
        
        print("[BACKTEST] Running in MULTI-SYMBOL mode")
        orchestrator.run_backtest(limit=args.limit)
    else:
        run_backtest(
            symbol=args.symbol,
            timeframe=args.timeframe,
            limit=args.limit,
            exchange_override=args.exchange
        )
