import os
import itertools
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import ccxt

from backtest import fetch_ohlcv_paged
from strategies.macd_only import add_indicators

# Env-driven defaults
BACKTEST_TIMEFRAME = os.getenv("BACKTEST_TIMEFRAME", "5m")
BACKTEST_LIMIT = int(os.getenv("BACKTEST_LIMIT", "20000"))
BACKTEST_EXCHANGE = os.getenv("BACKTEST_EXCHANGE", "okx")
BACKTEST_SYMBOL = os.getenv("BACKTEST_SYMBOL", "BTC/USDT")

LOGS_DIR = Path("logs")
RESULTS_PATH = LOGS_DIR / "macd_sweep_results.csv"
MIN_TRADES = 3



def add_indicators_parametric(df: pd.DataFrame, fast: int, slow: int, signal: int, rsi_period: int = 14) -> pd.DataFrame:
    """Compute MACD and RSI with configurable periods."""
    if fast == 12 and slow == 26 and signal == 9 and rsi_period == 14:
        # Use existing helper for default values
        return add_indicators(df)

    df = df.copy()
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    fast_ema = df["close"].ewm(span=fast, adjust=False).mean()
    slow_ema = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = fast_ema - slow_ema
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def generate_signal_parametric(df: pd.DataFrame, rsi_buy: float, rsi_exit: float) -> str:
    """MACD+RSI signal with adjustable RSI thresholds (new active version)."""
    if len(df) < 3:
        return "HOLD"

    # Access last two rows by position (iloc), not by index
    prev_idx = len(df) - 2
    curr_idx = len(df) - 1
    
    prev = df.iloc[prev_idx]
    curr = df.iloc[curr_idx]

    try:
        macd_prev = float(prev["macd"])
        macd_curr = float(curr["macd"])
        sig_prev = float(prev["macd_signal"])
        sig_curr = float(curr["macd_signal"])
        rsi_prev = float(prev["rsi"])
        rsi_curr = float(curr["rsi"])
    except (KeyError, ValueError, TypeError):
        return "HOLD"

    if any(pd.isna(x) for x in [macd_prev, macd_curr, sig_prev, sig_curr, rsi_prev, rsi_curr]):
        return "HOLD"

    # --- BUY logic ---
    macd_below_and_rising = (macd_curr < sig_curr) and (macd_curr > macd_prev)
    macd_bull_cross = (macd_prev <= sig_prev) and (macd_curr > sig_curr)

    rsi_oversold = rsi_curr <= rsi_buy
    rsi_recovering = (
        rsi_prev < rsi_buy
        and rsi_curr > rsi_prev
        and rsi_curr <= rsi_buy + 10.0
    )

    buy = (macd_below_and_rising or macd_bull_cross) and (rsi_oversold or rsi_recovering)

    # --- SELL logic ---
    macd_bear_cross = (macd_prev >= sig_prev) and (macd_curr < sig_curr)
    rsi_overbought = rsi_curr >= rsi_exit

    sell = macd_bear_cross or rsi_overbought

    if buy:
        return "BUY"
    if sell:
        return "SELL"
    return "HOLD"


def simulate(df: pd.DataFrame, fast: int, slow: int, signal: int, rsi_buy: int, rsi_exit: int) -> Dict[str, Any]:
    df = add_indicators_parametric(df, fast=fast, slow=slow, signal=signal, rsi_period=14)
    df = df.sort_values("timestamp").dropna()

    warmup = max(slow, signal, 14) + 2
    if len(df) <= warmup:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "final_equity": 0.0,
        }

    balance = 5000.0
    position = None
    entry_price = 0.0
    position_size = 0.0
    closed_trade_pnls: List[float] = []
    wins = 0
    losses = 0

    for i in range(warmup, len(df)):
        window = df.iloc[: i + 1]
        price = float(df.iloc[i]["close"])
        signal_out = generate_signal_parametric(window, rsi_buy=rsi_buy, rsi_exit=rsi_exit)

        if signal_out == "BUY" and position is None:
            risk_pct = 1.0
            notional = balance * (risk_pct / 100.0)
            position_size = notional / price
            entry_price = price
            position = "LONG"
        elif signal_out == "SELL" and position == "LONG":
            pnl = (price - entry_price) * position_size
            balance += pnl
            closed_trade_pnls.append(pnl)
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
            position = None
            entry_price = 0.0
            position_size = 0.0

    trades = wins + losses
    win_rate = (wins / trades * 100.0) if trades > 0 else 0.0
    total_pnl = sum(closed_trade_pnls)
    final_equity = balance if position is None else balance + (df.iloc[-1]["close"] - entry_price) * position_size

    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "final_equity": final_equity,
    }


def run_sweep():
    LOGS_DIR.mkdir(exist_ok=True)

    exchange_name = BACKTEST_EXCHANGE
    timeframe = BACKTEST_TIMEFRAME
    limit = BACKTEST_LIMIT

    # If BACKTEST_SYMBOL is set, use only that symbol; otherwise use defaults
    single_symbol = BACKTEST_SYMBOL
    if single_symbol:
        symbols = [single_symbol]
    else:
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    # MACD parameter grid (more active)
    fast_periods = [8, 12, 16]
    slow_periods = [21, 26, 35]
    signal_periods = [5, 9]

    # RSI thresholds: wider buy zone, looser exits
    rsi_buy_levels = [20, 25, 30, 35]
    rsi_exit_levels = [50, 55, 60, 65]

    param_grid = list(itertools.product(fast_periods, slow_periods, signal_periods, rsi_buy_levels, rsi_exit_levels))

    results: List[List[Any]] = []

    for symbol in symbols:
        print(f"\n=== Sweeping {symbol} ===")
        try:
            exchange = getattr(ccxt, exchange_name.lower())({"enableRateLimit": True})
        except AttributeError:
            print(f"[ERROR] Unknown exchange id: {exchange_name}")
            continue

        df_raw = fetch_ohlcv_paged(exchange, symbol, timeframe, limit)
        if df_raw.empty or len(df_raw) < 50:
            print(f"[ERROR] Not enough data for {symbol}. Skipping.")
            continue

        for fast, slow, sig, rsi_buy, rsi_exit in param_grid:
            stats = simulate(df_raw, fast=fast, slow=slow, signal=sig, rsi_buy=rsi_buy, rsi_exit=rsi_exit)
            results.append([
                symbol,
                timeframe,
                fast,
                slow,
                sig,
                rsi_buy,
                rsi_exit,
                stats["trades"],
                stats["wins"],
                stats["losses"],
                f"{stats['win_rate']:.2f}",
                f"{stats['total_pnl']:.4f}",
                f"{stats['final_equity']:.4f}",
            ])

    # Write CSV (append mode so each symbol's results accumulate)
    import csv
    
    file_exists = RESULTS_PATH.exists()
    with RESULTS_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        # Write header only if file is new
        if not file_exists:
            writer.writerow([
                "symbol",
                "timeframe",
                "fast",
                "slow",
                "signal",
                "rsi_buy",
                "rsi_exit",
                "trades",
                "wins",
                "losses",
                "win_rate",
                "total_pnl",
                "final_equity",
            ])
        
        for row in results:
            writer.writerow(row)

    combos_tested = len(results)
    combos_filtered = [r for r in results if int(r[7]) >= MIN_TRADES]
    print(f"\nTotal parameter combos tested: {combos_tested}")
    print(f"Configs with at least {MIN_TRADES} trades: {len(combos_filtered)}")

    top = sorted(combos_filtered, key=lambda r: (float(r[10]), float(r[11])), reverse=True)[:10]

    print(f"\nTop 10 configs (trades >= {MIN_TRADES}, sorted by win_rate then total_pnl):")
    print("symbol | fast | slow | signal | rsi_buy | rsi_exit | trades | wins | losses | win_rate | total_pnl | final_equity")
    for r in top:
        print(
            f"{r[0]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} | {r[8]} | {r[9]} | {r[10]} | {r[11]} | {r[12]}"
        )

    print(f"\nSweep results written to {RESULTS_PATH}")


def main():
    run_sweep()


if __name__ == "__main__":
    main()
