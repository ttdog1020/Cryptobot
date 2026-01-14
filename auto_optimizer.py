"""
MODULE 10: Auto-Optimizer for Degraded Symbols

Offline optimizer that:
1) Runs performance_report.py to refresh performance snapshots
2) Detects degraded symbols
3) Runs sweep_v3_params.py for those symbols
4) Picks best configuration and updates strategy_profiles.json
5) Logs updates to logs/strategy_updates.log
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd

# Paths / constants
PERF_JSON = Path("logs") / "perf_snapshot_latest.json"
STRATEGY_PROFILES = Path("strategy_profiles.json")
SWEEP_SCRIPT = "sweep_v3_params.py"
SWEEP_RESULTS = Path("logs") / "sweep_v3_results_auto.csv"
UPDATES_LOG = Path("logs") / "strategy_updates.log"

# Environment-based thresholds for Option D
AUTO_OPT_MIN_TRADES = int(os.getenv("AUTO_OPT_MIN_TRADES", "20"))
AUTO_OPT_MIN_WINRATE = float(os.getenv("AUTO_OPT_MIN_WINRATE", "40.0"))
AUTO_OPT_MIN_NETPNL = float(os.getenv("AUTO_OPT_MIN_NETPNL_USD", "-50.0"))

MIN_TRADES_SWEEP = AUTO_OPT_MIN_TRADES  # minimum trades for sweep config consideration

DEFAULT_TIMEFRAME = "15m"


def run_performance_snapshot():
    """Invoke performance_report.py to refresh snapshots."""
    subprocess.run([sys.executable, "-u", "performance_report.py"], check=True)


def load_perf_snapshot() -> Optional[pd.DataFrame]:
    """Load the performance snapshot JSON into a DataFrame."""
    if not PERF_JSON.exists():
        return None

    with PERF_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Normalize list vs object-with-rows
    if isinstance(data, dict) and "rows" in data:
        rows = data.get("rows", [])
    elif isinstance(data, list):
        rows = data
    else:
        rows = []

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Drop aggregate rows
    df = df[~df["symbol"].isin(["ALL", "PORTFOLIO"])] if "symbol" in df.columns else df

    # Ensure required columns exist
    for col in ["symbol", "trades", "win_rate_pct", "net_pnl", "profit_factor", "health_status"]:
        if col not in df.columns:
            df[col] = None

    # Numeric conversions
    for col in ["trades", "win_rate_pct", "net_pnl", "profit_factor"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Timeframe fallback
    if "timeframe" not in df.columns:
        df["timeframe"] = DEFAULT_TIMEFRAME
    df["timeframe"] = df["timeframe"].fillna(DEFAULT_TIMEFRAME)

    return df


def apply_forced_degraded(df: pd.DataFrame) -> pd.DataFrame:
    """Optionally force symbols into degraded status for testing via env AUTO_OPTIMIZER_FORCE_DEGRADED."""
    env_val = os.getenv("AUTO_OPTIMIZER_FORCE_DEGRADED", "").strip()
    if not env_val:
        return df

    forced = [s.strip() for s in env_val.split(",") if s.strip()]
    if not forced:
        return df

    df = df.copy()
    for sym in forced:
        mask = df["symbol"] == sym
        if mask.any():
            df.loc[mask, "health_status"] = "DEGRADED"
            df.loc[mask, "win_rate_pct"] = 30.0
            df.loc[mask, "net_pnl"] = -150.0
            df.loc[mask, "trades"] = df.loc[mask, "trades"].fillna(AUTO_OPT_MIN_TRADES).apply(
                lambda x: max(x, AUTO_OPT_MIN_TRADES)
            )
            print(f"[TEST] Forcing degraded status for {sym} via AUTO_OPTIMIZER_FORCE_DEGRADED")
        else:
            # If symbol not present, append a synthetic row
            df = pd.concat([
                df,
                pd.DataFrame([{
                    "symbol": sym,
                    "timeframe": DEFAULT_TIMEFRAME,
                    "trades": AUTO_OPT_MIN_TRADES,
                    "win_rate_pct": 30.0,
                    "net_pnl": -150.0,
                    "profit_factor": 0.5,
                    "health_status": "DEGRADED",
                }])
            ], ignore_index=True)
            print(f"[TEST] Added synthetic degraded row for {sym}")
    return df


def find_degraded_symbols(df: pd.DataFrame) -> List[Dict[str, str]]:
    degraded: List[Dict[str, str]] = []
    if df is None or df.empty:
        return degraded

    for _, row in df.iterrows():
        symbol = str(row.get("symbol", "")).strip()
        if not symbol:
            continue
        timeframe = str(row.get("timeframe", DEFAULT_TIMEFRAME)) or DEFAULT_TIMEFRAME

        trades = float(row.get("trades", 0) or 0)
        win_rate = float(row.get("win_rate_pct", 0) or 0)
        net_pnl = float(row.get("net_pnl", 0) or 0)

        # Must have minimum trades to be a candidate
        if trades < AUTO_OPT_MIN_TRADES:
            continue

        # Degraded if EITHER win_rate below threshold OR net_pnl below threshold
        degraded_flag = False
        if win_rate < AUTO_OPT_MIN_WINRATE:
            degraded_flag = True
        if net_pnl < AUTO_OPT_MIN_NETPNL:
            degraded_flag = True

        if degraded_flag:
            degraded.append({"symbol": symbol, "timeframe": timeframe})

    return degraded


def run_sweep_for_symbol(exchange: str, symbol: str, timeframe: str, limit: int = 20000) -> Optional[Path]:
    # Optional fast-path: reuse existing sweep output (for testing)
    if os.getenv("AUTO_OPTIMIZER_SKIP_SWEEP"):
        if SWEEP_RESULTS.exists():
            print(f"[SKIP] Using existing sweep results at {SWEEP_RESULTS}")
            return SWEEP_RESULTS
        default_path = Path("logs") / "sweep_v3_results.csv"
        if default_path.exists():
            print(f"[SKIP] Using existing sweep results at {default_path}")
            return default_path
        print("[SKIP] No sweep results available to reuse.")
        return None

    env = os.environ.copy()
    env["BACKTEST_EXCHANGE"] = exchange
    env["BACKTEST_SYMBOL"] = symbol
    env["BACKTEST_TIMEFRAME"] = timeframe
    env["BACKTEST_LIMIT"] = str(limit)
    env["SWEEP_OUTPUT"] = str(SWEEP_RESULTS)

    # Run sweep
    subprocess.run([sys.executable, "-u", SWEEP_SCRIPT], env=env, check=True)

    # Prefer custom sweep output, otherwise fallback to default
    if SWEEP_RESULTS.exists():
        return SWEEP_RESULTS
    default_path = Path("logs") / "sweep_v3_results.csv"
    return default_path if default_path.exists() else None


def pick_best_config(symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
    sweep_path = SWEEP_RESULTS if SWEEP_RESULTS.exists() else Path("logs") / "sweep_v3_results.csv"
    if not sweep_path.exists():
        print(f"[WARN] Sweep results not found: {sweep_path}")
        return None

    df = pd.read_csv(sweep_path)
    required_cols = [
        "symbol", "timeframe", "fast", "slow", "signal", "rsi_buy", "rsi_exit", "adx_min",
        "trades", "win_rate", "total_pnl", "final_equity"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"[WARN] Sweep results missing required columns: {missing}")
        return None

    df = df[(df["symbol"] == symbol) & (df["timeframe"] == timeframe)].copy()
    if df.empty:
        print(f"[WARN] No sweep rows for {symbol} {timeframe}")
        return None

    # Numeric conversions
    for col in ["trades", "win_rate", "total_pnl", "final_equity"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[df["trades"] >= MIN_TRADES_SWEEP]
    if df.empty:
        print(f"[WARN] No sweep rows with trades >= {MIN_TRADES_SWEEP} for {symbol} {timeframe}")
        return None

    df = df.sort_values(by=["win_rate", "total_pnl", "trades"], ascending=[False, False, False])
    row = df.iloc[0]
    return {
        "fast": int(row["fast"]),
        "slow": int(row["slow"]),
        "signal": int(row["signal"]),
        "rsi_buy": float(row["rsi_buy"]),
        "rsi_exit": float(row["rsi_exit"]),
        "adx_min": float(row["adx_min"]),
        "trades": float(row["trades"]),
        "win_rate": float(row["win_rate"]),
        "total_pnl": float(row["total_pnl"]),
        "final_equity": float(row["final_equity"]),
    }


def load_strategy_profiles() -> Dict[str, Dict[str, Dict[str, Any]]]:
    if not STRATEGY_PROFILES.exists():
        print(f"[WARN] strategy_profiles.json not found; starting with empty profiles")
        return {}
    with STRATEGY_PROFILES.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_strategy_profiles(profiles: Dict[str, Any]):
    STRATEGY_PROFILES.write_text(json.dumps(profiles, indent=2), encoding="utf-8")


def log_update(symbol: str, timeframe: str, old_params: Dict[str, Any], new_params: Dict[str, Any], metrics: Dict[str, Any]):
    UPDATES_LOG.parent.mkdir(exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "timeframe": timeframe,
        "reason": "DEGRADED",
        "old_profile": old_params,
        "new_profile": new_params,
        "metrics": metrics,
        "source": "auto_optimizer_v1",
    }
    with UPDATES_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> int:
    exchange = os.getenv("EXCHANGE", "okx")
    print("\n=== Module 10 Auto-Optimizer ===")

    # Step 1: regenerate performance snapshot (best-effort)
    try:
        run_performance_snapshot()
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] performance_report.py failed: {e}")
        # continue to check existing snapshot if present

    # Step 2: load snapshot (retry once if missing)
    df_perf = load_perf_snapshot()
    if df_perf is None:
        print("[WARN] Performance snapshot missing; rerunning performance_report.py once more...")
        try:
            run_performance_snapshot()
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] performance_report.py failed on retry: {e}")
        df_perf = load_perf_snapshot()
        if df_perf is None:
            print(f"[FATAL] Missing snapshot file: {PERF_JSON}")
            return 1

    # Optional test override
    df_perf = apply_forced_degraded(df_perf)

    # Step 3: detect degraded symbols
    degraded = find_degraded_symbols(df_perf)
    if not degraded:
        print("No degraded symbols; nothing to optimize.")
        return 0

    print(f"Degraded symbols detected: {[d['symbol'] for d in degraded]}")

    # Step 4: load profiles
    profiles = load_strategy_profiles()

    optimized = []
    skipped = []

    for item in degraded:
        symbol = item.get("symbol")
        timeframe = item.get("timeframe", DEFAULT_TIMEFRAME)
        print(f"\n[OPTIMIZE] {symbol} {timeframe}")

        # Ensure profile exists
        if symbol not in profiles or timeframe not in profiles.get(symbol, {}):
            print(f"[WARN] No existing profile for {symbol} {timeframe}; skipping")
            skipped.append(symbol)
            continue

        # Step 5: run sweep
        try:
            sweep_path = run_sweep_for_symbol(exchange, symbol, timeframe)
            if sweep_path:
                print(f"[INFO] Sweep completed -> {sweep_path}")
            else:
                print(f"[WARN] Sweep results missing after run; skipping {symbol}")
                skipped.append(symbol)
                continue
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Sweep failed for {symbol} {timeframe}: {e}")
            skipped.append(symbol)
            continue

        # Pick best config
        best = pick_best_config(symbol, timeframe)
        if not best:
            print(f"[WARN] No viable sweep config for {symbol} {timeframe}; skipping")
            skipped.append(symbol)
            continue

        # Update profiles
        old_params = profiles[symbol][timeframe]
        new_params = dict(old_params)
        for key in ["fast", "slow", "signal", "rsi_buy", "rsi_exit", "adx_min"]:
            new_params[key] = best[key]
        profiles[symbol][timeframe] = new_params
        save_strategy_profiles(profiles)

        # Log update
        metrics = {
            "trades": best.get("trades"),
            "win_rate": best.get("win_rate"),
            "total_pnl": best.get("total_pnl"),
            "final_equity": best.get("final_equity"),
        }
        log_update(symbol, timeframe, old_params, new_params, metrics)

        print(f"[UPDATED] {symbol} {timeframe} -> win_rate {best['win_rate']:.2f}%, pnl {best['total_pnl']:.2f}")
        optimized.append(symbol)

    # Portfolio summary
    print("\n=== Auto-Optimizer Summary ===")
    print(f"Optimized symbols: {optimized if optimized else 'None'}")
    print(f"Skipped symbols: {skipped if skipped else 'None'}")
    print(f"Updates log: {UPDATES_LOG}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
