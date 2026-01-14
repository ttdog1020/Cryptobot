"""
Quick Demo: Configuration-Driven Backtest

Demonstrates the config-driven backtest runner with a very small sample.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from backtests.config_backtest import run_config_backtest


def main():
    print("="*60)
    print("CONFIG-DRIVEN BACKTEST DEMO")
    print("="*60)
    print()
    print("This demo runs a quick backtest using:")
    print("  - Same config as live trading (config/live.yaml)")
    print("  - Same strategies, risk management, and execution logic")
    print("  - Cash+equity accounting model")
    print("  - Safety limits and kill switch")
    print()
    print("Running backtest for last 2 hours (small test)...")
    print("="*60)
    print()
    
    # Run backtest for last 2 hours
    end_date = datetime.now()
    start_date = end_date - timedelta(hours=2)
    
    try:
        results = run_config_backtest(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="1m"
        )
        
        print()
        print("="*60)
        print("DEMO COMPLETE")
        print("="*60)
        print()
        print("Results summary:")
        print(f"  Starting balance: ${results['performance']['starting_balance']:.2f}")
        print(f"  Final equity: ${results['performance']['equity']:.2f}")
        print(f"  Return: {results['performance']['total_return_pct']:+.2f}%")
        print(f"  Total trades: {results['performance']['total_trades']}")
        print()
        print(f"Trade log: {results['log_file']}")
        print()
        print("="*60)
        
    except Exception as e:
        print(f"Error running demo: {e}")
        print()
        print("Note: This demo requires network access to fetch market data.")
        print("If you see a rate limit error, try again in a few minutes.")


if __name__ == "__main__":
    main()
