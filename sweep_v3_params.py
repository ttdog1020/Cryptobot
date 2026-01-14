import os
import pandas as pd
from ta.trend import ADXIndicator
from fetch_ohlcv_paged import fetch_ohlcv_paged
from bot import BotConfig, create_exchange

FAST = [8, 12, 16]
SLOW = [21, 26, 35]
SIGNAL = [5, 7, 9]

RSI_BUY = [25, 30, 35]
RSI_EXIT = [55, 60, 65]

ADX_MIN = [15, 20, 25]

MIN_TRADES = 3

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

EXCHANGE = os.getenv("BACKTEST_EXCHANGE", "okx")
TIMEFRAME = os.getenv("BACKTEST_TIMEFRAME", "15m")
LIMIT = int(os.getenv("BACKTEST_LIMIT", "20000"))


def add_indicators_parametric(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.DataFrame:
    df = df.copy()
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    fast_ema = df["close"].ewm(span=fast, adjust=False).mean()
    slow_ema = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = fast_ema - slow_ema
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()

    df["rsi"] = df["close"].diff().pipe(lambda x: x.clip(lower=0)).ewm(alpha=1/14, adjust=False).mean() / (
        -df["close"].diff().clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
    )
    df["rsi"] = 100 - (100 / (1 + df["rsi"]))

    # ADX calculation (trend strength) - window 14
    adx_indicator = ADXIndicator(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )
    df["adx"] = adx_indicator.adx()
    
    return df


def generate_signal(df: pd.DataFrame, rsi_buy: float, rsi_exit: float, adx_min: float) -> str:
    if len(df) < 3:
        return "HOLD"
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    macd_prev, macd_curr = prev["macd"], curr["macd"]
    sig_prev, sig_curr = prev["macd_signal"], curr["macd_signal"]
    rsi_prev, rsi_curr = prev["rsi"], curr["rsi"]
    adx_curr = curr.get("adx", float("nan"))

    if pd.isna(macd_prev) or pd.isna(macd_curr) or pd.isna(sig_prev) or pd.isna(sig_curr) or pd.isna(rsi_curr):
        return "HOLD"
    if pd.isna(adx_curr) or adx_curr < adx_min:
        return "HOLD"

    macd_below_and_rising = (macd_curr < sig_curr) and (macd_curr > macd_prev)
    macd_bull_cross = (macd_prev <= sig_prev) and (macd_curr > sig_curr)
    rsi_oversold = rsi_curr <= rsi_buy
    rsi_recovering = (rsi_prev < rsi_buy) and (rsi_curr > rsi_prev) and (rsi_curr <= rsi_buy + 10)
    buy = (macd_below_and_rising or macd_bull_cross) and (rsi_oversold or rsi_recovering)

    macd_bear_cross = (macd_prev >= sig_prev) and (macd_curr < sig_curr)
    rsi_overbought = rsi_curr >= rsi_exit
    sell = macd_bear_cross or rsi_overbought

    if buy:
        return "BUY"
    if sell:
        return "SELL"
    return "HOLD"


def run_backtest(df: pd.DataFrame, fast: int, slow: int, signal: int, rsi_buy: float, rsi_exit: float, adx_min: float):
    df = add_indicators_parametric(df, fast, slow, signal).sort_values("timestamp").dropna()
    warmup = max(slow, signal, 14) + 2
    if len(df) <= warmup:
        return 0, 0, 0, 0.0, 0.0

    balance = 5000.0
    position = None
    entry_price = 0.0
    position_size = 0.0
    wins = 0
    losses = 0
    closed = []

    for i in range(warmup, len(df)):
        window = df.iloc[: i + 1]
        price = float(df.iloc[i]["close"])
        sig = generate_signal(window, rsi_buy, rsi_exit, adx_min)
        if sig == "BUY" and position is None:
            notional = balance * 0.01  # 1% risk per trade notionally
            position_size = notional / price
            entry_price = price
            position = "LONG"
        elif sig == "SELL" and position == "LONG":
            pnl = (price - entry_price) * position_size
            balance += pnl
            closed.append(pnl)
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
            position = None
            entry_price = 0.0
            position_size = 0.0

    trades = wins + losses
    win_rate = (wins / trades * 100.0) if trades > 0 else 0.0
    total_pnl = sum(closed)
    final_equity = balance if position is None else balance + (df.iloc[-1]["close"] - entry_price) * position_size
    return trades, wins, losses, total_pnl, final_equity


def main():
    # Build exchange instance (backtest mode, public data)
    cfg = BotConfig()
    cfg.exchange_name = EXCHANGE
    exchange = create_exchange(cfg)

    results = []
    for sym in SYMBOLS:
        print(f"=== Sweeping {sym} ===")
        candles = fetch_ohlcv_paged(exchange, sym, TIMEFRAME, LIMIT)
        if not candles or len(candles) < 50:
            print(f"[ERROR] No data for {sym}")
            continue

        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        for f in FAST:
            for s in SLOW:
                for sig in SIGNAL:
                    for rbuy in RSI_BUY:
                        for rexit in RSI_EXIT:
                            for adx_min in ADX_MIN:
                                trades, wins, losses, pnl, final_eq = run_backtest(
                                    df, f, s, sig, rbuy, rexit, adx_min
                                )
                                if trades >= MIN_TRADES:
                                    win_rate = (wins / trades) * 100.0 if trades else 0.0
                                    results.append([
                                        sym, TIMEFRAME, f, s, sig, rbuy, rexit, adx_min,
                                        trades, wins, losses, win_rate, pnl, final_eq
                                    ])

    os.makedirs("logs", exist_ok=True)
    outfile = "logs/sweep_v3_results.csv"
    pd.DataFrame(results, columns=[
        "symbol","timeframe","fast","slow","signal","rsi_buy","rsi_exit","adx_min",
        "trades","wins","losses","win_rate","total_pnl","final_equity"
    ]).to_csv(outfile, index=False)
    print(f"Completed sweep_v3. Results saved to {outfile}")


if __name__ == "__main__":
    main()
