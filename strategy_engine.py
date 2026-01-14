
import json
import os
import pathlib

DEFAULT_PATH = "strategy_profiles.json"

def load_profiles(path: str | None = None):
    """
    Load strategy profiles from JSON.
    Expected structure:
    {
      "ETH/USDT": {
        "15m": {
          "fast": 8,
          "slow": 26,
          "signal": 7,
          "rsi_buy": 35,
          "rsi_exit": 55,
          "adx_min": 20,
          "trades": 3,
          "win_rate": 100.0,
          "total_pnl": 1.93,
          "final_equity": 5001.93
        },
        ...
      },
      ...
    }
    """
    if path is None:
        path = DEFAULT_PATH
    p = pathlib.Path(path)
    if not p.exists():
        print(f"[STRATEGY] No strategy_profiles.json found at {p}, using empty profiles.")
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            print("[STRATEGY] strategy_profiles.json has unexpected format, using empty profiles.")
            return {}
        return data
    except Exception as e:
        print(f"[STRATEGY] Failed to load strategy profiles: {e}")
        return {}

def choose_profile(preferred_symbol: str | None = None, preferred_timeframe: str | None = None):
    """
    Choose a profile for (symbol, timeframe).

    Priority:
      1) If preferred symbol+timeframe exists -> use it.
      2) Else fall back to best (highest win_rate, then total_pnl) across all profiles.
    """
    profiles = load_profiles()
    symbol = None
    timeframe = None
    cfg = {}

    # Try preferred first
    if preferred_symbol and preferred_timeframe:
        sym_profiles = profiles.get(preferred_symbol)
        if isinstance(sym_profiles, dict):
            cfg = sym_profiles.get(preferred_timeframe, {})
            if cfg:
                symbol = preferred_symbol
                timeframe = preferred_timeframe

    # Fallback: best overall profile
    if not cfg:
        best = None
        best_key = (None, None)
        for sym, tfs in profiles.items():
            if not isinstance(tfs, dict):
                continue
            for tf, pcfg in tfs.items():
                if not isinstance(pcfg, dict):
                    continue
                win = float(pcfg.get("win_rate", 0.0))
                pnl = float(pcfg.get("total_pnl", 0.0))
                score = (win, pnl)
                if best is None or score > best:
                    best = score
                    best_key = (sym, tf)
        if best_key[0] is not None:
            symbol, timeframe = best_key
            cfg = profiles.get(symbol, {}).get(timeframe, {}) or {}

    return symbol, timeframe, cfg


def load_strategy_profile(symbol: str, timeframe: str):
    """
    Load a specific strategy profile for the given symbol and timeframe.
    Returns the profile dict if found, None otherwise.
    """
    profiles = load_profiles()
    sym_profiles = profiles.get(symbol)
    if isinstance(sym_profiles, dict):
        profile = sym_profiles.get(timeframe)
        if isinstance(profile, dict):
            return profile
    return None


def add_indicators(df, params=None):
    """
    Wrapper to load and call the appropriate add_indicators function based on strategy.
    Uses the strategy profile to determine which strategy module to load.
    """
    from strategies.macd_rsi_adx import add_indicators_macd_rsi_adx
    
    if params is None:
        params = {}
    return add_indicators_macd_rsi_adx(df, params)


def generate_signal_with_profile(df, bar_index, params=None):
    """
    Wrapper to generate a trading signal using the latest bar and the strategy profile.
    Accepts bar_index to slice df properly.
    """
    from strategies.macd_rsi_adx import generate_signal_macd_rsi_adx
    
    if params is None:
        params = {}
    
    if bar_index < 0 or bar_index >= len(df):
        return "HOLD"
    
    # Slice up to and including the bar_index
    df_slice = df.iloc[:bar_index + 1]
    return generate_signal_macd_rsi_adx(df_slice, params)
