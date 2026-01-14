"""
MODULE 9: Performance Analytics & Health Monitor

Analyzes trading performance across all symbols in logs/trades_multi.csv
and tracks equity drawdown from logs/equity_multi.csv.

Generates per-symbol performance metrics, health status, and timestamped snapshots.
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
import json

import pandas as pd
import numpy as np


# File paths
TRADES_LOG = Path("logs") / "trades_multi.csv"
EQUITY_LOG = Path("logs") / "equity_multi.csv"
PERF_SNAPSHOT_LATEST_CSV = Path("logs") / "perf_snapshot_latest.csv"
PERF_SNAPSHOT_LATEST_JSON = Path("logs") / "perf_snapshot_latest.json"


def load_trades_data():
    """Load and validate trades_multi.csv."""
    if not TRADES_LOG.exists():
        print(f"[ERROR] Trades log not found: {TRADES_LOG}")
        return None
    
    try:
        df = pd.read_csv(TRADES_LOG)
        if df.empty:
            print(f"[ERROR] Trades log is empty: {TRADES_LOG}")
            return None
        
        required_cols = ["symbol", "side", "pnl"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"[ERROR] Missing required columns in trades_multi.csv: {missing_cols}")
            return None
        
        return df
    except Exception as e:
        print(f"[ERROR] Failed to load trades log: {e}")
        return None


def load_equity_data():
    """Load and validate equity_multi.csv."""
    if not EQUITY_LOG.exists():
        print(f"[WARN] Equity log not found: {EQUITY_LOG}")
        return None
    
    try:
        df = pd.read_csv(EQUITY_LOG)
        if df.empty:
            print(f"[WARN] Equity log is empty: {EQUITY_LOG}")
            return None
        
        required_cols = ["symbol", "equity", "timestamp"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"[WARN] Missing required columns in equity_multi.csv: {missing_cols}")
            return None
        
        return df
    except Exception as e:
        print(f"[WARN] Failed to load equity log: {e}")
        return None


def compute_max_drawdown(equity_series):
    """
    Compute maximum drawdown in USD.
    
    Args:
        equity_series: pd.Series of equity values
    
    Returns:
        float: Maximum drawdown (negative value)
    """
    if equity_series.empty or len(equity_series) < 2:
        return 0.0
    
    # Convert to numeric, handling any formatting issues
    equity_values = pd.to_numeric(equity_series, errors='coerce')
    equity_values = equity_values.dropna()
    
    if equity_values.empty:
        return 0.0
    
    # Running max
    running_max = equity_values.expanding().max()
    drawdown = equity_values - running_max
    max_drawdown = drawdown.min()
    
    return max_drawdown


def compute_per_regime_metrics(trades_df):
    """
    Compute performance metrics per regime (if regime column exists).
    
    Args:
        trades_df: DataFrame from trades_multi.csv
    
    Returns:
        dict: {symbol: {regime: {metrics}}} or empty dict if no regime column
    """
    if "regime" not in trades_df.columns:
        return {}
    
    regime_metrics = {}
    symbols = trades_df["symbol"].unique()
    
    for symbol in symbols:
        symbol_trades = trades_df[trades_df["symbol"] == symbol].copy()
        symbol_trades["pnl"] = pd.to_numeric(symbol_trades["pnl"], errors='coerce')
        symbol_trades = symbol_trades.dropna(subset=["pnl"])
        
        if symbol not in regime_metrics:
            regime_metrics[symbol] = {}
        
        regimes = symbol_trades["regime"].unique()
        
        for regime in regimes:
            regime_trades = symbol_trades[symbol_trades["regime"] == regime]
            close_trades = regime_trades[regime_trades["side"] == "CLOSE_LONG"]
            
            trade_count = len(regime_trades)
            wins = len(close_trades[close_trades["pnl"] > 0])
            losses = len(close_trades[close_trades["pnl"] < 0])
            win_rate = (wins / trade_count * 100) if trade_count > 0 else 0.0
            
            net_pnl = regime_trades["pnl"].sum()
            
            profit_trades = close_trades[close_trades["pnl"] > 0]
            loss_trades = close_trades[close_trades["pnl"] < 0]
            
            gross_profit = profit_trades["pnl"].sum() if len(profit_trades) > 0 else 0.0
            gross_loss = abs(loss_trades["pnl"].sum()) if len(loss_trades) > 0 else 0.0
            
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None
            
            regime_metrics[symbol][regime] = {
                "trades": trade_count,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": win_rate,
                "net_pnl": net_pnl,
                "profit_factor": profit_factor
            }
    
    return regime_metrics


def compute_per_symbol_metrics(trades_df, equity_df):
    """
    Compute performance metrics per symbol.
    
    Args:
        trades_df: DataFrame from trades_multi.csv
        equity_df: DataFrame from equity_multi.csv (or None)
    
    Returns:
        dict: {symbol: {metrics dict}}
    """
    metrics = {}
    
    symbols = trades_df["symbol"].unique()
    
    for symbol in symbols:
        symbol_trades = trades_df[trades_df["symbol"] == symbol].copy()
        
        # Convert pnl to numeric
        symbol_trades["pnl"] = pd.to_numeric(symbol_trades["pnl"], errors='coerce')
        symbol_trades = symbol_trades.dropna(subset=["pnl"])
        
        trade_count = len(symbol_trades)
        
        if trade_count == 0:
            metrics[symbol] = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate_pct": 0.0,
                "net_pnl": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": None,
                "max_drawdown_usd": 0.0,
            }
            continue
        
        # Win/loss analysis (only count CLOSE trades)
        close_trades = symbol_trades[symbol_trades["side"] == "CLOSE_LONG"]
        
        wins = len(close_trades[close_trades["pnl"] > 0])
        losses = len(close_trades[close_trades["pnl"] < 0])
        win_rate = (wins / trade_count * 100) if trade_count > 0 else 0.0
        
        # PnL metrics (sum all trades for net, but analyze only closes for gross)
        net_pnl = symbol_trades["pnl"].sum()
        
        profit_trades = close_trades[close_trades["pnl"] > 0]
        loss_trades = close_trades[close_trades["pnl"] < 0]
        
        gross_profit = profit_trades["pnl"].sum() if len(profit_trades) > 0 else 0.0
        gross_loss = abs(loss_trades["pnl"].sum()) if len(loss_trades) > 0 else 0.0
        
        avg_win = (gross_profit / wins) if wins > 0 else 0.0
        avg_loss = (gross_loss / losses) if losses > 0 else 0.0
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None
        
        # Max drawdown
        max_drawdown = 0.0
        if equity_df is not None:
            symbol_equity = equity_df[equity_df["symbol"] == symbol].copy()
            if not symbol_equity.empty:
                symbol_equity = symbol_equity.sort_values("timestamp")
                max_drawdown = compute_max_drawdown(symbol_equity["equity"])
        
        metrics[symbol] = {
            "trades": trade_count,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": win_rate,
            "net_pnl": net_pnl,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "max_drawdown_usd": max_drawdown,
        }
    
    return metrics


def compute_aggregate_metrics(metrics_dict):
    """
    Compute aggregated metrics across all symbols.
    
    Args:
        metrics_dict: dict of {symbol: metrics}
    
    Returns:
        dict: aggregated metrics for "ALL"
    """
    if not metrics_dict:
        return {}
    
    total_trades = sum(m["trades"] for m in metrics_dict.values())
    total_wins = sum(m["wins"] for m in metrics_dict.values())
    total_losses = sum(m["losses"] for m in metrics_dict.values())
    total_net_pnl = sum(m["net_pnl"] for m in metrics_dict.values())
    total_gross_profit = sum(m["gross_profit"] for m in metrics_dict.values())
    total_gross_loss = sum(m["gross_loss"] for m in metrics_dict.values())
    
    total_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
    total_avg_win = (total_gross_profit / total_wins) if total_wins > 0 else 0.0
    total_avg_loss = (total_gross_loss / total_losses) if total_losses > 0 else 0.0
    total_profit_factor = (total_gross_profit / total_gross_loss) if total_gross_loss > 0 else None
    
    # Max drawdown is worst across all symbols
    all_drawdowns = [m["max_drawdown_usd"] for m in metrics_dict.values()]
    total_max_drawdown = min(all_drawdowns) if all_drawdowns else 0.0
    
    return {
        "trades": total_trades,
        "wins": total_wins,
        "losses": total_losses,
        "win_rate_pct": total_win_rate,
        "net_pnl": total_net_pnl,
        "gross_profit": total_gross_profit,
        "gross_loss": total_gross_loss,
        "avg_win": total_avg_win,
        "avg_loss": total_avg_loss,
        "profit_factor": total_profit_factor,
        "max_drawdown_usd": total_max_drawdown,
    }


def compute_health_status(trades, win_rate, net_pnl):
    """
    Determine health status based on performance metrics.
    
    Args:
        trades: int - number of trades
        win_rate: float - win rate percentage
        net_pnl: float - net profit/loss
    
    Returns:
        str: health status
    """
    if trades < 20:
        return "INSUFFICIENT_DATA"
    
    if win_rate >= 45 and net_pnl >= 0:
        return "HEALTHY"
    elif win_rate >= 35 and net_pnl > -100:
        return "WATCH"
    else:
        return "DEGRADED"


def create_report_dataframe(metrics_dict, include_all=True):
    """
    Create a DataFrame with performance metrics and health status.
    
    Args:
        metrics_dict: {symbol: metrics}
        include_all: bool - include aggregated "ALL" row
    
    Returns:
        pd.DataFrame
    """
    rows = []
    
    for symbol, m in sorted(metrics_dict.items()):
        health_status = compute_health_status(m["trades"], m["win_rate_pct"], m["net_pnl"])
        rows.append({
            "symbol": symbol,
            "trades": m["trades"],
            "wins": m["wins"],
            "losses": m["losses"],
            "win_rate_pct": m["win_rate_pct"],
            "net_pnl": m["net_pnl"],
            "gross_profit": m["gross_profit"],
            "gross_loss": m["gross_loss"],
            "avg_win": m["avg_win"],
            "avg_loss": m["avg_loss"],
            "profit_factor": m["profit_factor"],
            "max_drawdown_usd": m["max_drawdown_usd"],
            "health_status": health_status,
        })
    
    if include_all:
        all_metrics = compute_aggregate_metrics(metrics_dict)
        rows.append({
            "symbol": "ALL",
            "trades": all_metrics.get("trades", 0),
            "wins": all_metrics.get("wins", 0),
            "losses": all_metrics.get("losses", 0),
            "win_rate_pct": all_metrics.get("win_rate_pct", 0.0),
            "net_pnl": all_metrics.get("net_pnl", 0.0),
            "gross_profit": all_metrics.get("gross_profit", 0.0),
            "gross_loss": all_metrics.get("gross_loss", 0.0),
            "avg_win": all_metrics.get("avg_win", 0.0),
            "avg_loss": all_metrics.get("avg_loss", 0.0),
            "profit_factor": all_metrics.get("profit_factor"),
            "max_drawdown_usd": all_metrics.get("max_drawdown_usd", 0.0),
            "health_status": "PORTFOLIO",
        })
    
    return pd.DataFrame(rows)


def format_for_display(df):
    """
    Create a display version of the DataFrame with formatted strings.
    
    Args:
        df: DataFrame with raw numeric values
    
    Returns:
        DataFrame with formatted string values
    """
    display_df = df.copy()
    
    # Format USD columns to 2 decimals
    usd_cols = ["net_pnl", "gross_profit", "gross_loss", "avg_win", "avg_loss", "max_drawdown_usd"]
    for col in usd_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
    
    # Format win_rate_pct to 1 decimal + %
    if "win_rate_pct" in display_df.columns:
        display_df["win_rate_pct"] = display_df["win_rate_pct"].apply(lambda x: f"{x:.1f}%")
    
    # Format profit_factor to 2 decimals or "-"
    if "profit_factor" in display_df.columns:
        display_df["profit_factor"] = display_df["profit_factor"].apply(
            lambda x: f"{x:.2f}" if x is not None else "-"
        )
    
    return display_df


def print_report(df_raw, df_display):
    """
    Print performance report to console.
    
    Args:
        df_raw: DataFrame with raw values
        df_display: DataFrame with formatted strings
    """
    print("\n" + "="*120)
    print("=== Module 9: Performance Report ===")
    print("="*120 + "\n")
    
    # Column order for display
    cols_order = [
        "symbol", "trades", "wins", "losses", "win_rate_pct",
        "net_pnl", "gross_profit", "gross_loss",
        "avg_win", "avg_loss", "profit_factor", "max_drawdown_usd", "health_status"
    ]
    
    # Print table header
    print(f"{'Symbol':<12} {'Trades':>8} {'Wins':>6} {'Losses':>6} {'WinRate':>10} "
          f"{'Net PnL':>15} {'Gross Profit':>15} {'Gross Loss':>15} "
          f"{'Avg Win':>12} {'Avg Loss':>12} {'ProfitFactor':>13} {'Max DD':>12} {'Health':>18}")
    print("-" * 190)
    
    for idx, row in df_display.iterrows():
        raw_row = df_raw.iloc[idx]
        print(f"{row['symbol']:<12} {raw_row['trades']:>8} {raw_row['wins']:>6} {raw_row['losses']:>6} "
              f"{row['win_rate_pct']:>10} "
              f"{row['net_pnl']:>15} {row['gross_profit']:>15} {row['gross_loss']:>15} "
              f"{row['avg_win']:>12} {row['avg_loss']:>12} {row['profit_factor']:>13} "
              f"{row['max_drawdown_usd']:>12} {row['health_status']:>18}")
    
    print("-" * 190)
    print()


def print_regime_breakdown(regime_metrics):
    """
    Print per-regime performance breakdown.
    
    Args:
        regime_metrics: dict from compute_per_regime_metrics
    """
    if not regime_metrics:
        return  # No regime data
    
    print("=== Per-Regime Breakdown ===\n")
    
    for symbol, regimes in regime_metrics.items():
        print(f"{symbol}:")
        
        # Sort regimes for consistent display
        for regime in sorted(regimes.keys()):
            metrics = regimes[regime]
            pf = f"{metrics['profit_factor']:.2f}" if metrics['profit_factor'] is not None else "-"
            
            print(f"  {regime:12} | Trades: {metrics['trades']:3} | "
                  f"WR: {metrics['win_rate_pct']:5.1f}% | "
                  f"PnL: ${metrics['net_pnl']:10.2f} | "
                  f"PF: {pf:>6}")
        
        print()


def print_health_summary(df_raw):
    """
    Print health status summary.
    
    Args:
        df_raw: DataFrame with raw values
    """
    print("=== Health Summary ===\n")
    
    for idx, row in df_raw.iterrows():
        symbol = row["symbol"]
        health = row["health_status"]
        win_rate = row["win_rate_pct"]
        net_pnl = row["net_pnl"]
        max_dd = row["max_drawdown_usd"]
        
        if health == "HEALTHY":
            status_label = "OK"
        elif health == "WATCH":
            status_label = "WATCH"
        elif health == "DEGRADED":
            status_label = "DEGRADED"
        else:
            status_label = "INFO"

        print(f"{status_label:8} {symbol:12} -> {health:18} (WR: {win_rate:6.1f}%, PnL: ${net_pnl:>10.2f}, DD: ${max_dd:>10.2f})")
    
    print()


def save_snapshots(df_raw):
    """
    Save performance snapshots to CSV and JSON.
    
    Args:
        df_raw: DataFrame with raw values
    """
    # Prepare data for export
    export_df = df_raw.copy()
    
    # CSV snapshot
    export_df.to_csv(PERF_SNAPSHOT_LATEST_CSV, index=False)
    print(f"[SNAPSHOT] Saved: {PERF_SNAPSHOT_LATEST_CSV}")
    
    # JSON snapshot (records format)
    records = export_df.to_dict(orient="records")
    with open(PERF_SNAPSHOT_LATEST_JSON, "w") as f:
        json.dump(records, f, indent=2, default=str)
    print(f"[SNAPSHOT] Saved: {PERF_SNAPSHOT_LATEST_JSON}")
    
    # Timestamped JSON snapshot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_json = Path("logs") / f"perf_snapshot_{timestamp}.json"
    with open(timestamped_json, "w") as f:
        json.dump(records, f, indent=2, default=str)
    print(f"[SNAPSHOT] Saved: {timestamped_json}")
    print()


def main(quiet: bool = False):
    """Main entry point."""
    if not quiet:
        print("[MODULE 9] Starting Performance Analytics & Health Monitor...")
    
    # Load data
    trades_df = load_trades_data()
    if trades_df is None:
        if not quiet:
            print("\n[ERROR] Cannot proceed without trades data. Exiting.")
        return 1
    
    equity_df = load_equity_data()
    
    # Compute metrics
    metrics = compute_per_symbol_metrics(trades_df, equity_df)
    
    if not metrics:
        if not quiet:
            print("[ERROR] No symbols found in trades data. Exiting.")
        return 1
    
    # Create report DataFrame
    df_raw = create_report_dataframe(metrics, include_all=True)
    df_display = format_for_display(df_raw)
    
    # Compute per-regime metrics (if regime column exists)
    regime_metrics = compute_per_regime_metrics(trades_df)
    
    # Print report (skip in quiet mode)
    if not quiet:
        print_report(df_raw, df_display)
        print_health_summary(df_raw)
        print_regime_breakdown(regime_metrics)
    
    # Save snapshots
    save_snapshots(df_raw)
    
    if not quiet:
        print("[MODULE 9] Performance report generated successfully.")
    else:
        print("[PERF] Snapshot updated.")
    
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Performance Analytics & Health Monitor")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output; only generate snapshots")
    args = parser.parse_args()
    
    sys.exit(main(quiet=args.quiet))
