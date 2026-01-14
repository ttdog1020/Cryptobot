"""
MODULE 19: Paper Trade Report (with Module 20 Safety Integration)

CLI tool for analyzing and reporting paper trading performance.
Includes invariant validation for accounting integrity.

Usage:
    python analytics/paper_report.py --log-file path/to/log.csv
    python analytics/paper_report.py --log-file path/to/log.csv --group-by-symbol
    python analytics/paper_report.py --log-file path/to/log.csv --output report.json
    python -m analytics.paper_report --log-file path/to/log.csv --group-by-symbol
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
import numpy as np

# Import invariant checks (Module 20)
try:
    from validation.invariants import check_accounting_invariants
    INVARIANTS_AVAILABLE = True
except ImportError:
    INVARIANTS_AVAILABLE = False
    print("Warning: validation.invariants not available. Skipping safety checks.")


class PaperTradeReport:
    """
    Analyzes paper trading logs and generates performance reports.
    
    Features:
    - Overall PnL, win rate, trade count
    - Max drawdown calculation
    - Per-symbol performance breakdown
    - R-multiple analysis (if available)
    - Console and JSON output
    """
    
    def __init__(self, log_file: Path):
        """
        Initialize report from CSV log file.
        
        Args:
            log_file: Path to paper trading CSV log
        """
        self.log_file = Path(log_file)
        self.df: Optional[pd.DataFrame] = None
        self.trades_df: Optional[pd.DataFrame] = None
        self.starting_balance: Optional[float] = None
        self.final_balance: Optional[float] = None
        self.final_equity: Optional[float] = None
        
        self._load_data()
    
    def _load_data(self):
        """Load and validate CSV data."""
        if not self.log_file.exists():
            raise FileNotFoundError(f"Log file not found: {self.log_file}")
        
        try:
            self.df = pd.read_csv(self.log_file)
            
            # Validate required columns
            required_cols = ['timestamp', 'symbol', 'action', 'side', 'quantity', 
                           'fill_price', 'balance', 'equity']
            missing = set(required_cols) - set(self.df.columns)
            if missing:
                raise ValueError(f"Missing required columns: {missing}")
            
            # Convert timestamp
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
            
            # Extract starting/final balance
            if len(self.df) > 0:
                # Use INIT row if available for true starting balance
                init_rows = self.df[self.df['action'] == 'INIT']
                if not init_rows.empty:
                    self.starting_balance = init_rows.iloc[0]['balance']
                else:
                    self.starting_balance = self.df.iloc[0]['equity']  # Fallback to first equity
                
                self.final_balance = self.df.iloc[-1]['balance']
                self.final_equity = self.df.iloc[-1]['equity']
            
            # Filter for closed trades only (action == CLOSE)
            if 'action' in self.df.columns:
                self.trades_df = self.df[self.df['action'] == 'CLOSE'].copy()
            else:
                # Fallback: assume every other row is a close
                self.trades_df = self.df[::2].copy() if len(self.df) > 1 else pd.DataFrame()
            
            # Run invariant checks (Module 20 safety integration)
            self._run_invariant_checks()
                
        except Exception as e:
            raise ValueError(f"Error loading CSV: {e}")
    
    def _run_invariant_checks(self):
        """
        Run accounting invariant checks on loaded data (Module 20 integration).
        
        Prints warnings if invariants fail but doesn't stop execution.
        This provides an additional safety layer on top of the accounting fix.
        """
        if not INVARIANTS_AVAILABLE:
            return
        
        if self.df.empty or self.starting_balance is None:
            return
        
        try:
            check_accounting_invariants(
                self.df,
                self.starting_balance,
                epsilon=0.01
            )
        except AssertionError as e:
            # Print warning but continue
            print("\n" + "!"*70)
            print("ACCOUNTING INVARIANT VIOLATION DETECTED")
            print("!"*70)
            print(f"\n{e}\n")
            print("This indicates a potential accounting error in the trading log.")
            print("Please review the log file for discrepancies.")
            print("!"*70 + "\n")
    
    def get_overall_metrics(self) -> Dict[str, Any]:
        """Calculate overall performance metrics."""
        if self.df is None or len(self.df) == 0:
            return {
                'total_pnl': 0.0,
                'total_pnl_pct': 0.0,
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_r_multiple': None,
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
                'avg_trade_pnl': 0.0,
                'starting_balance': 0.0,
                'final_balance': 0.0,
                'final_equity': 0.0
            }
        
        # Overall PnL
        total_pnl = self.final_equity - self.starting_balance
        total_pnl_pct = (total_pnl / self.starting_balance * 100) if self.starting_balance > 0 else 0.0
        
        # Trade count (closed trades only)
        total_trades = len(self.trades_df)
        
        # Win rate
        if total_trades > 0 and 'realized_pnl' in self.trades_df.columns:
            winning_trades = len(self.trades_df[self.trades_df['realized_pnl'] > 0])
            win_rate = (winning_trades / total_trades) * 100
            
            # Largest win/loss
            largest_win = self.trades_df['realized_pnl'].max()
            largest_loss = self.trades_df['realized_pnl'].min()
            avg_trade_pnl = self.trades_df['realized_pnl'].mean()
        else:
            win_rate = 0.0
            largest_win = 0.0
            largest_loss = 0.0
            avg_trade_pnl = 0.0
        
        # R-multiple (if available - approximate using PnL percentage)
        avg_r_multiple = None
        if total_trades > 0 and 'pnl_pct' in self.trades_df.columns:
            # R-multiple approximation: assume 1R = 1% risk
            avg_r_multiple = self.trades_df['pnl_pct'].mean()
        
        # Max drawdown (equity-based)
        max_dd, max_dd_pct = self._calculate_max_drawdown()
        
        return {
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_r_multiple': avg_r_multiple,
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd_pct,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'avg_trade_pnl': avg_trade_pnl,
            'starting_balance': self.starting_balance,
            'final_balance': self.final_balance,
            'final_equity': self.final_equity
        }
    
    def _calculate_max_drawdown(self) -> tuple:
        """Calculate maximum drawdown from equity curve."""
        if self.df is None or len(self.df) == 0:
            return 0.0, 0.0
        
        equity = self.df['equity'].values
        running_max = np.maximum.accumulate(equity)
        drawdown = running_max - equity
        max_dd = drawdown.max()
        
        # Percentage drawdown
        max_dd_idx = drawdown.argmax()
        peak_equity = running_max[max_dd_idx]
        max_dd_pct = (max_dd / peak_equity * 100) if peak_equity > 0 else 0.0
        
        return max_dd, max_dd_pct
    
    def get_per_symbol_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Calculate per-symbol performance metrics."""
        if self.trades_df is None or len(self.trades_df) == 0:
            return {}
        
        per_symbol = {}
        
        for symbol in self.trades_df['symbol'].unique():
            symbol_trades = self.trades_df[self.trades_df['symbol'] == symbol]
            
            num_trades = len(symbol_trades)
            
            if 'realized_pnl' in symbol_trades.columns:
                total_pnl = symbol_trades['realized_pnl'].sum()
                avg_pnl = symbol_trades['realized_pnl'].mean()
                winning = len(symbol_trades[symbol_trades['realized_pnl'] > 0])
                win_rate = (winning / num_trades * 100) if num_trades > 0 else 0.0
            else:
                total_pnl = 0.0
                avg_pnl = 0.0
                win_rate = 0.0
            
            per_symbol[symbol] = {
                'trades': num_trades,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'win_rate': win_rate
            }
        
        return per_symbol
    
    def print_report(self, group_by_symbol: bool = False):
        """Print formatted report to console."""
        metrics = self.get_overall_metrics()
        
        print("\n" + "="*70)
        print("PAPER TRADING PERFORMANCE REPORT")
        print("="*70)
        print(f"Log File: {self.log_file}")
        
        if len(self.df) > 0:
            session_start = self.df.iloc[0]['timestamp']
            session_end = self.df.iloc[-1]['timestamp']
            duration = session_end - session_start
            print(f"Session Start: {session_start}")
            print(f"Session End: {session_end}")
            print(f"Duration: {duration}")
        
        print("\n" + "-"*70)
        print("OVERALL PERFORMANCE")
        print("-"*70)
        
        # Warn if no INIT row found
        if self.df[self.df['action'] == 'INIT'].empty:
            print("  WARNING: No INIT row found. Starting balance may be inaccurate.")
            print("     (Upgrade to latest PaperTrader for accurate reporting)\n")
        
        # Module 25: Display multi-symbol allocation clarity
        num_symbols = len(self.df['symbol'].unique()) if not self.df.empty else 0
        if metrics['starting_balance'] == 10000.0 and num_symbols == 10:
            print("  (Implied allocation: ~$1,000 per symbol across 10 symbols)\n")
        
        print(f"  Starting Balance:     ${metrics['starting_balance']:,.2f}")
        print(f"  Final Balance:        ${metrics['final_balance']:,.2f}")
        print(f"  Final Equity:         ${metrics['final_equity']:,.2f}")
        print(f"  Total PnL:            ${metrics['total_pnl']:,.2f} ({metrics['total_pnl_pct']:+.2f}%)")
        print(f"  Total Trades:         {metrics['total_trades']}")
        print(f"  Win Rate:             {metrics['win_rate']:.1f}%")
        print(f"  Average Trade PnL:    ${metrics['avg_trade_pnl']:,.2f}")
        print(f"  Largest Win:          ${metrics['largest_win']:,.2f}")
        print(f"  Largest Loss:         ${metrics['largest_loss']:,.2f}")
        print(f"  Max Drawdown:         ${metrics['max_drawdown']:,.2f} ({metrics['max_drawdown_pct']:.2f}%)")
        
        if metrics['avg_r_multiple'] is not None:
            print(f"  Avg R-Multiple:       {metrics['avg_r_multiple']:.2f}R")
        
        # Per-symbol breakdown
        if group_by_symbol:
            per_symbol = self.get_per_symbol_metrics()
            
            if per_symbol:
                print("\n" + "-"*70)
                print("PER-SYMBOL BREAKDOWN")
                print("-"*70)
                
                for symbol, stats in sorted(per_symbol.items()):
                    print(f"\n  {symbol}:")
                    print(f"    Trades:        {stats['trades']}")
                    print(f"    Total PnL:     ${stats['total_pnl']:,.2f}")
                    print(f"    Avg PnL:       ${stats['avg_pnl']:,.2f}")
                    print(f"    Win Rate:      {stats['win_rate']:.1f}%")
        
        print("\n" + "="*70)
        
        # Friendly message if no trades
        if metrics['total_trades'] == 0:
            print("\nNo completed trades found in this session.")
            print("   Trades are counted when positions are CLOSED.\n")
    
    def save_report(self, output_path: Path, group_by_symbol: bool = False):
        """Save report to JSON file."""
        metrics = self.get_overall_metrics()
        
        report = {
            'log_file': str(self.log_file),
            'timestamp': datetime.now().isoformat(),
            'overall': metrics
        }
        
        if group_by_symbol:
            report['per_symbol'] = self.get_per_symbol_metrics()
        
        # Add session info
        if len(self.df) > 0:
            report['session'] = {
                'start': self.df.iloc[0]['timestamp'].isoformat(),
                'end': self.df.iloc[-1]['timestamp'].isoformat(),
                'duration_seconds': (self.df.iloc[-1]['timestamp'] - self.df.iloc[0]['timestamp']).total_seconds()
            }
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Report saved to: {output_path}")


def generate_report(
    log_file: str,
    group_by_symbol: bool = False,
    output: Optional[str] = None
):
    """
    Generate paper trading report.
    
    Args:
        log_file: Path to CSV log file
        group_by_symbol: Include per-symbol breakdown
        output: Optional path to save JSON report
    """
    try:
        report = PaperTradeReport(Path(log_file))
        report.print_report(group_by_symbol=group_by_symbol)
        
        if output:
            report.save_report(Path(output), group_by_symbol=group_by_symbol)
    
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Generate paper trading performance report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analytics/paper_report.py --log-file logs/paper_trades/paper_trades_20251208_120000.csv
  python analytics/paper_report.py --log-file logs/paper_trades/paper_trades_20251208_120000.csv --group-by-symbol
  python analytics/paper_report.py --log-file logs/paper_trades/paper_trades_20251208_120000.csv --output report.json
  python -m analytics.paper_report --log-file logs/paper_trades/paper_trades_20251208_120000.csv --group-by-symbol
        """
    )
    
    parser.add_argument(
        '--log-file',
        type=str,
        required=True,
        help='Path to paper trading CSV log file'
    )
    
    parser.add_argument(
        '--group-by-symbol',
        action='store_true',
        help='Include per-symbol performance breakdown'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Path to save JSON report (optional, default is console only)'
    )
    
    args = parser.parse_args()
    
    generate_report(
        log_file=args.log_file,
        group_by_symbol=args.group_by_symbol,
        output=args.output
    )


if __name__ == '__main__':
    main()
