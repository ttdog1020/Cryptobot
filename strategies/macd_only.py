import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add indicators needed for the MACD+RSI dip strategy:
    - MACD (12, 26, 9)
    - RSI(14)
    """
    df = df.copy()

    # Ensure numeric price columns
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # MACD
    fast_ema = df["close"].ewm(span=12, adjust=False).mean()
    slow_ema = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = fast_ema - slow_ema
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # RSI(14) – Wilder-style
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    df["rsi"] = 100 - (100 / (1 + rs))

    return df


def generate_signal(df: pd.DataFrame, rsi_buy: float = 40.0, rsi_exit: float = 60.0) -> str:
    """
    More active MACD + RSI signal:
      - BUY when MACD is below its signal but rising (or just crossed up)
        AND RSI is oversold or recovering from an oversold area.
      - SELL when MACD crosses down or RSI reaches an exit/overbought band.
    """
    # Need at least 3 candles for a stable signal
    if len(df) < 3:
        return "HOLD"

    last2 = df.iloc[-2:]
    prev = last2.iloc[0]
    curr = last2.iloc[1]

    macd_prev = float(prev["macd"])
    macd_curr = float(curr["macd"])
    sig_prev = float(prev["macd_signal"])
    sig_curr = float(curr["macd_signal"])
    rsi_prev = float(prev["rsi"])
    rsi_curr = float(curr["rsi"])

    # --- BUY logic ---
    # MACD is still below the signal line but turning up, OR just crossed above.
    macd_below_and_rising = (macd_curr < sig_curr) and (macd_curr > macd_prev)
    macd_bull_cross = (macd_prev <= sig_prev) and (macd_curr > sig_curr)

    # RSI is clearly oversold, OR it is recovering from a low area
    # and still below (rsi_buy + 10) to keep entries relatively low.
    rsi_oversold = rsi_curr <= rsi_buy
    rsi_recovering = (
        rsi_prev < rsi_buy
        and rsi_curr > rsi_prev
        and rsi_curr <= rsi_buy + 10.0
    )

    buy = (macd_below_and_rising or macd_bull_cross) and (rsi_oversold or rsi_recovering)

    # --- SELL logic ---
    # Exit either on a MACD bear cross or on RSI hitting the exit band.
    macd_bear_cross = (macd_prev >= sig_prev) and (macd_curr < sig_curr)
    rsi_overbought = rsi_curr >= rsi_exit

    sell = macd_bear_cross or rsi_overbought

    if buy:
        return "BUY"
    if sell:
        return "SELL"
    return "HOLD"
