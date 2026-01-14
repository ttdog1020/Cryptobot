import pandas as pd
import numpy as np

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Ensure numeric
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # EMA 20 / 50
    df["ema_fast"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=50, adjust=False).mean()

    # RSI 14
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100.0 - (100.0 / (1.0 + rs))

    # ATR 14
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    df["atr"] = tr.ewm(span=14, adjust=False).mean()

    # MACD (12,26,9)
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    return df

def generate_signal(df: pd.DataFrame) -> str:
    """
    More active MACD + RSI strategy:
      - BUY when MACD is above signal (or just crossed above) AND RSI <= 45
      - SELL when MACD is below signal (or just crossed below) OR RSI >= 60

    Uses the last two CLOSED candles.
    """
    if len(df) < 3:
        return "HOLD"

    # operate on time-sorted closed candles
    df = df.sort_values("timestamp")

    macd_prev = df["macd"].iloc[-2]
    macd_cur = df["macd"].iloc[-1]
    sig_prev = df["macd_signal"].iloc[-2]
    sig_cur = df["macd_signal"].iloc[-1]

    rsi_prev = df["rsi"].iloc[-2]
    rsi_cur = df["rsi"].iloc[-1]

    # MACD cross / direction
    bull_cross = macd_prev <= sig_prev and macd_cur > sig_cur
    bear_cross = macd_prev >= sig_prev and macd_cur < sig_cur

    macd_turning_up = macd_cur > macd_prev
    macd_turning_down = macd_cur < macd_prev

    # RSI zones (more active than the previous dip-only logic)
    rsi_soft_oversold = rsi_cur <= 60
    rsi_recovering = rsi_prev < rsi_cur <= 60

    rsi_rolling_over = rsi_prev > rsi_cur and rsi_cur >= 50
    rsi_overbought = rsi_cur >= 70

    # BUY:
    # - MACD is crossing up or turning up
    # - RSI is at or below ~60 (not too hot) and ideally recovering
    if (bull_cross or (macd_turning_up and macd_cur > sig_cur)) and (rsi_soft_oversold or rsi_recovering):
        return "BUY"

    # SELL:
    # - MACD crosses down or turns down
    # - RSI is rolling over from 50+ or clearly overbought
    if bear_cross and (rsi_rolling_over or rsi_overbought):
        return "SELL"
    if macd_turning_down and macd_cur < sig_cur and (rsi_rolling_over or rsi_overbought):
        return "SELL"

    return "HOLD"
