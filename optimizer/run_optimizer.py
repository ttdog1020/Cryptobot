"""
MODULE 30 + 31 + 32: Strategy Optimizer CLI with Auto-Apply and Performance History

Command-line interface for running parameter search optimization.
Module 31 adds auto-apply functionality to write optimized profiles.
Module 32 adds performance history logging for strategy evolution.

Usage:
    # Basic optimization run
    python optimizer/run_optimizer.py --start 2025-11-01 --end 2025-12-01

    # Multi-symbol with custom max runs
    python optimizer/run_optimizer.py --start 2025-11-01 --end 2025-12-01 --symbols BTCUSDT ETHUSDT --max-runs 10

    # Auto-apply optimized profiles (Module 31)
    python optimizer/run_optimizer.py --start 2025-11-01 --end 2025-12-01 --auto-apply --min-trades 10 --max-dd-pct 5.0

    # Disable performance history logging (Module 32)
    python optimizer/run_optimizer.py --start 2025-11-01 --end 2025-12-01 --no-log-history

    # Save results to CSV
    python optimizer/run_optimizer.py --start 2025-11-01 --end 2025-12-01 --output logs/optimizer/my_results.csv

Example output:
    TOP 5 PARAMETER SETS
    ====================
    Rank  Score     Trades  Win%   Params
    1     +12.34%   45      67.5%  {'ema_fast': 8, 'ema_slow': 21, 'rsi_overbought': 70}
    2     +10.21%   38      65.0%  {'ema_fast': 12, 'ema_slow': 26, 'rsi_overbought': 70}
    ...

Performance History:
    Each optimization run is logged to logs/performance_history/history.jsonl
    This enables:
    - Tracking optimization performance over time
    - Comparing current profiles against historical alternatives
    - Detecting profile decay (degraded performance)
    
    Use --no-log-history to disable this feature.
"""

import argparse
import sys
import logging
import csv
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from optimizer.param_search import run_param_search, OptimizationRunConfig
from strategies.profile_loader import StrategyProfileLoader
from optimizer import performance_history

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


# Default parameter grid for scalping_ema_rsi strategy
# RSI ranges slightly loosened to increase trade frequency for live trading,
# safety is enforced via risk engine + evolution thresholds.
DEFAULT_PARAM_GRID = {
    "ema_fast": [8, 12, 16],
    "ema_slow": [21, 26, 34],
    "rsi_overbought": [60, 62, 64, 66, 68, 70, 72],
    "rsi_oversold": [28, 30, 32, 34, 36, 38, 40],
}


def print_top_results(results, top_n: int = 5):
    """
    Print top N results in a formatted table.
    
    Args:
        results: List of optimization results
        top_n: Number of top results to display
    """
    print("\n" + "="*100)
    print(f"TOP {top_n} PARAMETER SETS")
    print("="*100)
    
    # Header
    print(f"{'Rank':<6} {'Score':<10} {'Trades':<8} {'Win%':<8} {'MaxDD%':<8} {'Params':<50}")
    print("-"*100)
    
    # Print top N
    for i, result in enumerate(results[:top_n], 1):
        score = result['score']
        metrics = result['metrics']
        params = result['params']
        
        # Format params as compact string
        param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
        if len(param_str) > 48:
            param_str = param_str[:45] + "..."
        
        print(f"{i:<6} {score:+8.2f}%  {metrics['total_trades']:<8} "
              f"{metrics['win_rate']:<7.1f}% {metrics['max_drawdown_pct']:<7.2f}% {param_str:<50}")
    
    print("="*100)


def save_results_to_csv(results, output_path: Path):
    """
    Save full results to CSV file.
    
    Args:
        results: List of optimization results
        output_path: Path to output CSV file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', newline='') as f:
        # Determine all parameter names
        param_names = list(results[0]['params'].keys()) if results else []
        
        # CSV columns (include all metrics fields)
        fieldnames = ['rank', 'score'] + param_names + [
            'total_return_pct', 'total_pnl', 'total_trades', 'win_rate', 
            'max_drawdown_pct', 'avg_trade_pnl', 'largest_win', 'largest_loss', 
            'symbols', 'log_file'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for i, result in enumerate(results, 1):
            # Extract metric values explicitly
            metrics = result['metrics']
            row = {
                'rank': i,
                'score': result['score'],
                **result['params'],
                'total_return_pct': metrics.get('total_return_pct', 0),
                'total_pnl': metrics.get('total_pnl', 0),
                'total_trades': metrics.get('total_trades', 0),
                'win_rate': metrics.get('win_rate', 0),
                'max_drawdown_pct': metrics.get('max_drawdown_pct', 0),
                'avg_trade_pnl': metrics.get('avg_trade_pnl', 0),
                'largest_win': metrics.get('largest_win', 0),
                'largest_loss': metrics.get('largest_loss', 0),
                'symbols': ','.join(result['symbols']),
                'log_file': result.get('log_file', '')
            }
            writer.writerow(row)
    
    logger.info(f"Results saved to: {output_path}")


def group_results_by_symbol(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group optimization results by symbol.
    
    Args:
        results: List of optimization results
        
    Returns:
        Dictionary mapping symbol -> list of results for that symbol
    """
    grouped = {}
    
    for result in results:
        # Each result has a 'symbols' list
        symbols = result.get('symbols', [])
        for symbol in symbols:
            if symbol not in grouped:
                grouped[symbol] = []
            grouped[symbol].append(result)
    
    return grouped


def apply_profiles(
    results: List[Dict[str, Any]],
    profile_dir: str,
    min_trades: int,
    max_dd_pct: float,
    min_return_pct: float
) -> Dict[str, Dict[str, Any]]:
    """
    Apply optimized profiles with safety filters.
    
    Args:
        results: List of optimization results
        profile_dir: Directory to save profile files
        min_trades: Minimum number of trades required
        max_dd_pct: Maximum drawdown percentage allowed
        min_return_pct: Minimum return percentage required
        
    Returns:
        Dictionary mapping symbol -> application result (status, params, metrics, reason)
    """
    loader = StrategyProfileLoader(profile_dir=profile_dir)
    grouped = group_results_by_symbol(results)
    application_results = {}
    
    for symbol, symbol_results in grouped.items():
        # Find best candidate that passes filters
        best_candidate = None
        rejection_reasons = []
        
        for result in symbol_results:
            metrics = result['metrics']
            trades = metrics.get('total_trades', 0)
            dd_pct = metrics.get('max_drawdown_pct', 0)
            return_pct = metrics.get('total_return_pct', 0)
            
            # Apply safety filters
            if trades < min_trades:
                rejection_reasons.append(f"trades {trades} < {min_trades}")
                continue
            
            if dd_pct > max_dd_pct:
                rejection_reasons.append(f"max_dd {dd_pct:.2f}% > {max_dd_pct}%")
                continue
            
            if return_pct < min_return_pct:
                rejection_reasons.append(f"return {return_pct:.2f}% < {min_return_pct}%")
                continue
            
            # Passed all filters
            best_candidate = result
            break
        
        if best_candidate:
            # Write profile
            params = best_candidate['params']
            metrics = {
                'total_return_pct': best_candidate['metrics'].get('total_return_pct', 0),
                'max_dd_pct': best_candidate['metrics'].get('max_drawdown_pct', 0),
                'trades': best_candidate['metrics'].get('total_trades', 0),
                'win_rate_pct': best_candidate['metrics'].get('win_rate', 0),
                'avg_trade_pnl': best_candidate['metrics'].get('avg_trade_pnl', 0)
            }
            
            profile_path = loader.save_profile(
                symbol=symbol,
                strategy="scalping_ema_rsi",
                params=params,
                metrics=metrics,
                source="optimizer",  # Module 32: updated from "optimizer_v1"
                enabled=True
            )
            
            logger.info(f"[OK] Applied optimized profile for {symbol} → {profile_path}")
            
            application_results[symbol] = {
                'status': 'applied',
                'selected_params': params,
                'metrics': metrics,
                'profile_path': str(profile_path)
            }
        else:
            # No candidate passed filters
            reason = rejection_reasons[0] if rejection_reasons else "no valid candidates"
            logger.warning(f"[WARN] No safe parameter set for {symbol} (failed filters: {reason})")
            
            application_results[symbol] = {
                'status': 'rejected',
                'reason': reason,
                'rejection_details': rejection_reasons[:3]  # Top 3 rejection reasons
            }
    
    return application_results


def save_audit_log(
    args: argparse.Namespace,
    application_results: Dict[str, Dict[str, Any]],
    total_runs: int
) -> Path:
    """
    Save optimizer audit log to JSON file.
    
    Args:
        args: CLI arguments
        application_results: Results from apply_profiles()
        total_runs: Total number of optimization runs
        
    Returns:
        Path to saved audit log
    """
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    audit_log = {
        'timestamp': timestamp,
        'args': {
            'start': args.start,
            'end': args.end,
            'symbols': args.symbols,
            'interval': args.interval,
            'auto_apply': args.auto_apply,
            'min_trades': args.min_trades,
            'max_dd_pct': args.max_dd_pct,
            'min_return_pct': args.min_return_pct,
            'max_runs': args.max_runs,
            'total_runs_executed': total_runs
        },
        'results': application_results
    }
    
    # Create audit log directory
    audit_dir = Path("logs/optimizer")
    audit_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_path = audit_dir / f"optimizer_run_{run_timestamp}.json"
    
    # Write audit log (pretty-printed)
    with open(audit_path, 'w', encoding='utf-8') as f:
        json.dump(audit_log, f, indent=2, ensure_ascii=False)
    
    logger.info(f"[OK] Audit log saved: {audit_path}")
    
    return audit_path


def build_run_summary(
    args,
    results: List[Dict[str, Any]],
    application_results: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build run summary dict for performance history logging.
    
    Args:
        args: Parsed CLI arguments
        results: List of optimization results (sorted by score)
        application_results: Optional auto-apply results (Module 31)
    
    Returns:
        Run summary dict matching performance_history schema
    """
    # Load risk config snapshot
    risk_config_path = Path("config/risk.json")
    if risk_config_path.exists():
        with open(risk_config_path, 'r') as f:
            risk_config_snapshot = json.load(f)
    else:
        risk_config_snapshot = None
        logger.warning(f"Risk config not found: {risk_config_path}")
    
    # Load trailing stop settings from trading_mode.yaml (if exists)
    trading_mode_path = Path("config/trading_mode.yaml")
    trailing_stop_enabled = False
    trailing_stop_pct = None
    if trading_mode_path.exists():
        try:
            with open(trading_mode_path, 'r') as f:
                trading_mode = yaml.safe_load(f) or {}
            trailing_stop_enabled = trading_mode.get('trailing_stop_enabled', False)
            trailing_stop_pct = trading_mode.get('trailing_stop_pct')
        except Exception as e:
            logger.warning(f"Failed to load trading_mode.yaml: {e}")
    
    # Build profiles list with metrics and rankings
    profiles = []
    for rank, result in enumerate(results, 1):
        # Get symbol from result (use symbols list or args)
        result_symbols = result.get('symbols', args.symbols)
        # For single-symbol runs, use the first symbol; for multi-symbol, this will be in the result
        symbol = result_symbols[0] if result_symbols else 'UNKNOWN'
        
        # Determine if this profile was selected for live trading
        selected_for_live = False
        if application_results and symbol in application_results:
            selected_for_live = (application_results[symbol]['status'] == 'applied')
        
        profile = {
            "symbol": symbol,
            "params": result['params'],
            "metrics": {
                "total_trades": result['metrics']['total_trades'],
                "win_rate_pct": result['metrics']['win_rate'],
                "total_return_pct": result['score'],  # score is already return %
                "max_drawdown_pct": result['metrics']['max_drawdown_pct'],
                "avg_R_multiple": result['metrics'].get('avg_R_multiple', 0.0)
            },
            "ranked_position": rank,
            "selected_for_live": selected_for_live
        }
        profiles.append(profile)
    
    # Generate run ID
    run_id = performance_history.generate_run_id()
    
    # Build run summary
    run_summary = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "scalping_ema_rsi",
        "symbols": args.symbols,
        "start": args.start,
        "end": args.end,
        "interval": args.interval,
        "trailing_stop_enabled": trailing_stop_enabled,
        "trailing_stop_pct": trailing_stop_pct,
        "risk_config_snapshot": risk_config_snapshot,
        "profiles": profiles
    }
    
    return run_summary


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Strategy parameter optimization using grid search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Optimize over 1 month period
  python optimizer/run_optimizer.py --start 2025-11-01 --end 2025-12-01

  # Multi-symbol optimization
  python optimizer/run_optimizer.py --start 2025-11-01 --end 2025-12-01 --symbols BTCUSDT ETHUSDT SOLUSDT

  # Limit number of runs and save results
  python optimizer/run_optimizer.py --start 2025-11-01 --end 2025-12-01 --max-runs 20 --output logs/optimizer/results.csv

  # Quick test with 1 week of data
  python optimizer/run_optimizer.py --start 2025-12-01 --end 2025-12-08
        """
    )
    
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD format)"
    )
    
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="End date (YYYY-MM-DD format)"
    )
    
    parser.add_argument(
        "--symbols",
        type=str,
        nargs='+',
        default=["BTCUSDT"],
        help="Symbols to optimize (space-separated, default: BTCUSDT)"
    )
    
    parser.add_argument(
        "--interval",
        type=str,
        default="1m",
        help="Candle interval (default: 1m)"
    )
    
    parser.add_argument(
        "--max-runs",
        type=int,
        help="Maximum number of parameter combinations to test (optional)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        help="Path to save CSV results (optional, default: logs/optimizer/optimizer_results_YYYYMMDD_YYYYMMDD.csv)"
    )
    
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="Number of top results to display (default: 5)"
    )
    
    # Module 31: Auto-apply arguments
    parser.add_argument(
        "--auto-apply",
        action="store_true",
        help="Automatically apply optimized profiles to config/strategy_profiles/ (Module 31)"
    )
    
    parser.add_argument(
        "--profile-dir",
        type=str,
        default="config/strategy_profiles",
        help="Directory to save strategy profiles (default: config/strategy_profiles)"
    )
    
    parser.add_argument(
        "--min-trades",
        type=int,
        default=10,
        help="Minimum number of trades required to accept a parameter set (default: 10)"
    )
    
    parser.add_argument(
        "--max-dd-pct",
        type=float,
        default=5.0,
        help="Maximum drawdown percentage allowed (default: 5.0)"
    )
    
    parser.add_argument(
        "--min-return-pct",
        type=float,
        default=0.0,
        help="Minimum return percentage required (default: 0.0)"
    )
    
    # Module 32: Performance history logging
    parser.add_argument(
        "--no-log-history",
        action="store_true",
        help="Disable performance history logging (Module 32)"
    )
    
    args = parser.parse_args()
    
    try:
        # Parse dates
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
        end_date = datetime.strptime(args.end, "%Y-%m-%d")
        
        # Create optimization config
        config = OptimizationRunConfig(
            symbols=args.symbols,
            start=start_date,
            end=end_date,
            interval=args.interval,
            param_grid=DEFAULT_PARAM_GRID,
            max_runs=args.max_runs,
            label="scalping_ema_rsi_opt"
        )
        
        # Run optimization
        results = run_param_search(config)
        
        if not results:
            logger.error("No results generated!")
            sys.exit(1)
        
        # Print top results
        print_top_results(results, top_n=args.top_n)
        
        # Save to CSV
        if args.output:
            output_path = Path(args.output)
        else:
            # Default output path
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
            output_path = Path(f"logs/optimizer/optimizer_results_{start_str}_{end_str}.csv")
        
        save_results_to_csv(results, output_path)
        
        # Module 31: Auto-apply profiles if enabled
        if args.auto_apply:
            logger.info("\n" + "="*60)
            logger.info("MODULE 31: Applying Optimized Profiles")
            logger.info("="*60)
            logger.info(f"Safety filters: min_trades={args.min_trades}, "
                       f"max_dd_pct={args.max_dd_pct}%, min_return_pct={args.min_return_pct}%")
            
            application_results = apply_profiles(
                results=results,
                profile_dir=args.profile_dir,
                min_trades=args.min_trades,
                max_dd_pct=args.max_dd_pct,
                min_return_pct=args.min_return_pct
            )
            
            # Save audit log
            audit_path = save_audit_log(
                args=args,
                application_results=application_results,
                total_runs=len(results)
            )
            
            # Summary
            applied_count = sum(1 for r in application_results.values() if r['status'] == 'applied')
            rejected_count = sum(1 for r in application_results.values() if r['status'] == 'rejected')
            
            print("\n" + "="*60)
            print("AUTO-APPLY SUMMARY")
            print("="*60)
            print(f"  Applied:  {applied_count} profile(s)")
            print(f"  Rejected: {rejected_count} candidate(s)")
            print(f"  Audit log: {audit_path}")
            print("="*60)
        
        # Module 32: Log performance history (unless disabled)
        if not args.no_log_history:
            try:
                logger.info("\n" + "="*60)
                logger.info("MODULE 32: Logging Performance History")
                logger.info("="*60)
                
                # Build run summary
                run_summary = build_run_summary(
                    args=args,
                    results=results,
                    application_results=application_results if args.auto_apply else None
                )
                
                # Log to history
                performance_history.log_run(run_summary)
                
                history_path = performance_history.get_history_dir() / "history.jsonl"
                logger.info(f"[OK] Performance history logged: {history_path}")
                logger.info(f"     Run ID: {run_summary['run_id']}")
                logger.info(f"     Profiles logged: {len(run_summary['profiles'])}")
                
            except Exception as e:
                logger.error(f"Failed to log performance history: {e}", exc_info=True)
                # Don't fail the entire run if history logging fails
        
        # Summary
        print(f"\n✅ Optimization complete!")
        print(f"   Best score: {results[0]['score']:+.2f}%")
        print(f"   Best params: {results[0]['params']}")
        print(f"   Full results: {output_path}")
        
    except KeyboardInterrupt:
        logger.info("\nOptimization interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Optimization failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
