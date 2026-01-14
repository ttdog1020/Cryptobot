"""
Decay Detector for Strategy Profiles (Module 32 Step 4)

Analyzes strategy profile health by comparing current metrics
against historical optimizer performance. Flags profiles that
are degraded relative to known-good configurations.

READ-ONLY: This module ONLY reports status, never modifies configs.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional, Any

from optimizer.performance_history import get_history_dir, load_history
from strategies.profile_loader import StrategyProfileLoader

logger = logging.getLogger(__name__)

# Status types
StatusType = Literal["healthy", "degraded", "no-data", "error"]


@dataclass
class DecayStatus:
    """
    Status of a strategy profile's health.
    
    Attributes:
        symbol: Trading pair (e.g., "BTCUSDT")
        strategy: Strategy name (e.g., "scalping_ema_rsi")
        status: Health status ("healthy", "degraded", "no-data", "error")
        reason: Human-readable explanation
        stats: Dictionary with comparison metrics
    """
    symbol: str
    strategy: str
    status: StatusType
    reason: str
    stats: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


async def analyze_profile_decay(
    symbol: str,
    strategy: str,
    profile_dir: Optional[Path] = None,
    history_dir: Optional[Path] = None,
    min_trades: int = 50,
    max_lookback_days: int = 30,
    winrate_threshold_pct: float = 15.0,
    drawdown_threshold_pct: float = 10.0
) -> DecayStatus:
    """
    Analyze a strategy profile for performance decay.
    
    Compares current profile metrics against historical optimizer results
    to determine if the profile is still performing well or has degraded.
    
    Args:
        symbol: Trading pair to analyze
        strategy: Strategy name
        profile_dir: Directory with strategy profiles (default: config/strategy_profiles)
        history_dir: Directory with performance history (default: logs/performance_history)
        min_trades: Minimum trades required for analysis
        max_lookback_days: Maximum age of history records to consider
        winrate_threshold_pct: Maximum allowed win rate drop (percentage points)
        drawdown_threshold_pct: Maximum allowed drawdown increase (percentage points)
        
    Returns:
        DecayStatus with health assessment
    """
    try:
        # Default paths
        if profile_dir is None:
            profile_dir = Path("config/strategy_profiles")
        if history_dir is None:
            history_dir = get_history_dir()
        
        # Load current profile
        loader = StrategyProfileLoader(profile_dir)
        profile = loader.load_profile(symbol, strategy, require_enabled=False)
        
        if profile is None:
            return DecayStatus(
                symbol=symbol,
                strategy=strategy,
                status="no-data",
                reason=f"No profile found for {symbol}",
                stats={}
            )
        
        # Get current metrics
        current_metrics = profile.get("metrics", {})
        current_trades = current_metrics.get("trades", 0)
        current_winrate = current_metrics.get("win_rate_pct", 0.0)
        current_return = current_metrics.get("total_return_pct", 0.0)
        current_drawdown = current_metrics.get("max_drawdown_pct", 0.0)
        
        # Check if current profile has enough trades
        if current_trades < min_trades:
            return DecayStatus(
                symbol=symbol,
                strategy=strategy,
                status="no-data",
                reason=f"Insufficient trades ({current_trades} < {min_trades})",
                stats={
                    "current_trades": current_trades,
                    "min_trades": min_trades
                }
            )
        
        # Load performance history
        history = load_history(history_dir=history_dir)
        
        if not history:
            return DecayStatus(
                symbol=symbol,
                strategy=strategy,
                status="no-data",
                reason="No performance history found",
                stats={"current_trades": current_trades}
            )
        
        # Filter history for relevant runs
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_lookback_days)
        relevant_runs = []
        
        for run in history:
            # Parse timestamp
            created_at_str = run.get("created_at", "")
            try:
                # Remove 'Z' suffix and parse with UTC timezone
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                # Ensure timezone-aware
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue
            
            # Check if within lookback window
            if created_at < cutoff_date:
                continue
            
            # Check if strategy matches
            if run.get("strategy") != strategy:
                continue
            
            # Find matching symbol profile in this run
            for profile_entry in run.get("profiles", []):
                if profile_entry.get("symbol") != symbol:
                    continue
                
                # Check if profile has enough trades
                profile_metrics = profile_entry.get("metrics", {})
                if profile_metrics.get("trades", 0) < min_trades:
                    continue
                
                relevant_runs.append({
                    "run_id": run.get("run_id"),
                    "created_at": created_at_str,
                    "metrics": profile_metrics
                })
        
        if not relevant_runs:
            return DecayStatus(
                symbol=symbol,
                strategy=strategy,
                status="no-data",
                reason=f"No historical runs found with >={min_trades} trades in last {max_lookback_days} days",
                stats={
                    "current_trades": current_trades,
                    "lookback_days": max_lookback_days
                }
            )
        
        # Find best historical metrics
        best_winrate = max(r["metrics"].get("win_rate_pct", 0.0) for r in relevant_runs)
        best_return = max(r["metrics"].get("total_return_pct", 0.0) for r in relevant_runs)
        best_drawdown = min(r["metrics"].get("max_drawdown_pct", 100.0) for r in relevant_runs)
        
        # Calculate degradation
        winrate_drop = best_winrate - current_winrate
        drawdown_increase = current_drawdown - best_drawdown
        
        # Determine status
        degradation_reasons = []
        
        if winrate_drop > winrate_threshold_pct:
            degradation_reasons.append(
                f"Win rate dropped {winrate_drop:.1f}% "
                f"(current: {current_winrate:.1f}%, best: {best_winrate:.1f}%)"
            )
        
        if drawdown_increase > drawdown_threshold_pct:
            degradation_reasons.append(
                f"Max drawdown increased {drawdown_increase:.1f}% "
                f"(current: {current_drawdown:.1f}%, best: {best_drawdown:.1f}%)"
            )
        
        # Build stats
        stats = {
            "current_trades": current_trades,
            "current_winrate_pct": current_winrate,
            "current_return_pct": current_return,
            "current_drawdown_pct": current_drawdown,
            "best_winrate_pct": best_winrate,
            "best_return_pct": best_return,
            "best_drawdown_pct": best_drawdown,
            "winrate_drop_pct": winrate_drop,
            "drawdown_increase_pct": drawdown_increase,
            "num_historical_runs": len(relevant_runs),
            "lookback_days": max_lookback_days,
            "thresholds": {
                "min_trades": min_trades,
                "winrate_threshold_pct": winrate_threshold_pct,
                "drawdown_threshold_pct": drawdown_threshold_pct
            }
        }
        
        if degradation_reasons:
            return DecayStatus(
                symbol=symbol,
                strategy=strategy,
                status="degraded",
                reason="; ".join(degradation_reasons),
                stats=stats
            )
        else:
            return DecayStatus(
                symbol=symbol,
                strategy=strategy,
                status="healthy",
                reason=f"Metrics within thresholds (checked {len(relevant_runs)} historical runs)",
                stats=stats
            )
    
    except Exception as e:
        logger.exception(f"Error analyzing decay for {symbol}: {e}")
        return DecayStatus(
            symbol=symbol,
            strategy=strategy,
            status="error",
            reason=f"Analysis failed: {str(e)}",
            stats={}
        )
