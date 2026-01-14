"""
CLI for running decay detection on strategy profiles (Module 32)

Usage:
    python -m optimizer.run_decay_check --symbol BTCUSDT
    python -m optimizer.run_decay_check --symbol ETHUSDT --min-trades 100
    python -m optimizer.run_decay_check --all
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

from optimizer.decay_detector import analyze_profile_decay, DecayStatus
from strategies.profile_loader import StrategyProfileLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def format_status(status: DecayStatus) -> str:
    """Format DecayStatus for console output"""
    lines = []
    lines.append("=" * 70)
    lines.append(f"Symbol: {status.symbol}")
    lines.append(f"Strategy: {status.strategy}")
    lines.append(f"Status: {status.status.upper()}")
    lines.append(f"Reason: {status.reason}")
    lines.append("")
    
    if status.stats:
        lines.append("Metrics:")
        stats = status.stats
        
        # Current metrics
        if "current_trades" in stats:
            lines.append(f"  Current Trades: {stats['current_trades']}")
        if "current_winrate_pct" in stats:
            lines.append(f"  Current Win Rate: {stats['current_winrate_pct']:.2f}%")
        if "current_return_pct" in stats:
            lines.append(f"  Current Total Return: {stats['current_return_pct']:.2f}%")
        if "current_drawdown_pct" in stats:
            lines.append(f"  Current Max Drawdown: {stats['current_drawdown_pct']:.2f}%")
        
        # Historical best
        if "best_winrate_pct" in stats:
            lines.append("")
            lines.append("Historical Best:")
            lines.append(f"  Best Win Rate: {stats['best_winrate_pct']:.2f}%")
        if "best_return_pct" in stats:
            lines.append(f"  Best Total Return: {stats['best_return_pct']:.2f}%")
        if "best_drawdown_pct" in stats:
            lines.append(f"  Best Max Drawdown: {stats['best_drawdown_pct']:.2f}%")
        
        # Degradation
        if "winrate_drop_pct" in stats:
            lines.append("")
            lines.append("Degradation:")
            lines.append(f"  Win Rate Drop: {stats['winrate_drop_pct']:.2f}%")
        if "drawdown_increase_pct" in stats:
            lines.append(f"  Drawdown Increase: {stats['drawdown_increase_pct']:.2f}%")
        
        # Analysis context
        if "num_historical_runs" in stats:
            lines.append("")
            lines.append("Analysis Context:")
            lines.append(f"  Historical Runs: {stats['num_historical_runs']}")
        if "lookback_days" in stats:
            lines.append(f"  Lookback Days: {stats['lookback_days']}")
        
        # Thresholds
        if "thresholds" in stats:
            thresholds = stats["thresholds"]
            lines.append("")
            lines.append("Thresholds:")
            if "min_trades" in thresholds:
                lines.append(f"  Min Trades: {thresholds['min_trades']}")
            if "winrate_threshold_pct" in thresholds:
                lines.append(f"  Win Rate Threshold: {thresholds['winrate_threshold_pct']:.1f}%")
            if "drawdown_threshold_pct" in thresholds:
                lines.append(f"  Drawdown Threshold: {thresholds['drawdown_threshold_pct']:.1f}%")
    
    lines.append("=" * 70)
    return "\n".join(lines)


async def check_symbol(
    symbol: str,
    strategy: str,
    min_trades: int,
    max_lookback_days: int,
    winrate_threshold: float,
    drawdown_threshold: float
) -> DecayStatus:
    """Check a single symbol"""
    logger.info(f"Analyzing {symbol} for decay...")
    
    status = await analyze_profile_decay(
        symbol=symbol,
        strategy=strategy,
        min_trades=min_trades,
        max_lookback_days=max_lookback_days,
        winrate_threshold_pct=winrate_threshold,
        drawdown_threshold_pct=drawdown_threshold
    )
    
    print(format_status(status))
    return status


async def check_all_symbols(
    strategy: str,
    profile_dir: Path,
    min_trades: int,
    max_lookback_days: int,
    winrate_threshold: float,
    drawdown_threshold: float
) -> list[DecayStatus]:
    """Check all symbols with profiles"""
    loader = StrategyProfileLoader(profile_dir)
    profiles = loader.load_all_profiles(strategy, require_enabled=False)
    
    if not profiles:
        logger.warning(f"No profiles found in {profile_dir}")
        return []
    
    logger.info(f"Found {len(profiles)} profiles to analyze")
    
    results = []
    for symbol in profiles.keys():
        status = await check_symbol(
            symbol=symbol,
            strategy=strategy,
            min_trades=min_trades,
            max_lookback_days=max_lookback_days,
            winrate_threshold=winrate_threshold,
            drawdown_threshold=drawdown_threshold
        )
        results.append(status)
    
    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    healthy_count = sum(1 for s in results if s.status == "healthy")
    degraded_count = sum(1 for s in results if s.status == "degraded")
    no_data_count = sum(1 for s in results if s.status == "no-data")
    error_count = sum(1 for s in results if s.status == "error")
    
    print(f"Total Profiles: {len(results)}")
    print(f"Healthy: {healthy_count}")
    print(f"Degraded: {degraded_count}")
    print(f"No Data: {no_data_count}")
    print(f"Errors: {error_count}")
    print("=" * 70)
    
    return results


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Analyze strategy profiles for performance decay (Module 32)"
    )
    
    parser.add_argument(
        "--symbol",
        type=str,
        help="Symbol to analyze (e.g., BTCUSDT). If not provided with --all, required."
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Analyze all symbols with profiles"
    )
    
    parser.add_argument(
        "--strategy",
        type=str,
        default="scalping_ema_rsi",
        help="Strategy name (default: scalping_ema_rsi)"
    )
    
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=Path("config/strategy_profiles"),
        help="Directory with strategy profiles (default: config/strategy_profiles)"
    )
    
    parser.add_argument(
        "--min-trades",
        type=int,
        default=50,
        help="Minimum trades required for analysis (default: 50)"
    )
    
    parser.add_argument(
        "--max-lookback-days",
        type=int,
        default=30,
        help="Maximum age of history records in days (default: 30)"
    )
    
    parser.add_argument(
        "--winrate-threshold",
        type=float,
        default=15.0,
        help="Max allowed win rate drop in percentage points (default: 15.0)"
    )
    
    parser.add_argument(
        "--drawdown-threshold",
        type=float,
        default=10.0,
        help="Max allowed drawdown increase in percentage points (default: 10.0)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.all and not args.symbol:
        parser.error("Either --symbol or --all must be provided")
    
    if args.all:
        results = await check_all_symbols(
            strategy=args.strategy,
            profile_dir=args.profile_dir,
            min_trades=args.min_trades,
            max_lookback_days=args.max_lookback_days,
            winrate_threshold=args.winrate_threshold,
            drawdown_threshold=args.drawdown_threshold
        )
        
        # Exit with error code if any degraded
        degraded_count = sum(1 for s in results if s.status == "degraded")
        if degraded_count > 0:
            logger.warning(f"{degraded_count} profile(s) are degraded")
            sys.exit(1)
    else:
        status = await check_symbol(
            symbol=args.symbol,
            strategy=args.strategy,
            min_trades=args.min_trades,
            max_lookback_days=args.max_lookback_days,
            winrate_threshold=args.winrate_threshold,
            drawdown_threshold=args.drawdown_threshold
        )
        
        # Exit with error code if degraded
        if status.status == "degraded":
            sys.exit(1)
    
    logger.info("Decay check complete")


if __name__ == "__main__":
    asyncio.run(main())
