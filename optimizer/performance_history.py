"""
MODULE 32: Performance History Tracker

Persists detailed performance history for optimizer runs to enable
decay detection and profile evolution tracking.

Each optimization run is logged as a single JSON line in:
    logs/performance_history/history.jsonl

Schema for each entry:
    {
        "run_id": "unique_id",
        "created_at": "2025-12-08T12:00:00Z",
        "strategy": "scalping_ema_rsi",
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "start": "2025-12-01",
        "end": "2025-12-08",
        "interval": "1m",
        "trailing_stop_enabled": true,
        "trailing_stop_pct": 2.0,
        "risk_config_snapshot": {
            "default_risk_per_trade_pct": 1.0,
            "max_exposure_pct": 20.0,
            "max_daily_loss_pct": 5.0,
            "max_open_trades": 3
        },
        "profiles": [
            {
                "symbol": "BTCUSDT",
                "params": {...},
                "profile_name": "BTCUSDT.json",
                "metrics": {
                    "trades": 25,
                    "win_rate_pct": 65.0,
                    "total_return_pct": 12.3,
                    "max_drawdown_pct": 2.5,
                    "avg_R_multiple": 1.8
                },
                "ranked_position": 1,
                "selected_for_live": false
            }
        ]
    }
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import uuid

logger = logging.getLogger(__name__)


def get_history_dir() -> Path:
    """
    Get performance history directory.
    
    Returns:
        Path to logs/performance_history (creates if missing)
    """
    history_dir = Path("logs/performance_history")
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir


def log_run(run_summary: dict) -> Path:
    """
    Append a single optimization run record to history.jsonl.
    
    Args:
        run_summary: Dictionary with run metadata and results
        
    Returns:
        Path to history file
        
    Raises:
        ValueError: If required fields are missing
    """
    # Validate required fields
    required_fields = [
        'run_id', 'created_at', 'strategy', 'symbols',
        'start', 'end', 'interval', 'profiles'
    ]
    
    missing_fields = [f for f in required_fields if f not in run_summary]
    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")
    
    # Validate profiles structure
    if not isinstance(run_summary['profiles'], list):
        raise ValueError("'profiles' must be a list")
    
    for profile in run_summary['profiles']:
        required_profile_fields = ['symbol', 'params', 'metrics', 'ranked_position']
        missing = [f for f in required_profile_fields if f not in profile]
        if missing:
            raise ValueError(f"Profile missing fields: {missing}")
    
    # Get history file path
    history_file = get_history_dir() / "history.jsonl"
    
    # Append as single JSON line (thread-safe with 'a' mode)
    with open(history_file, 'a', encoding='utf-8') as f:
        json.dump(run_summary, f, ensure_ascii=False)
        f.write('\n')
    
    logger.info(f"Logged optimization run {run_summary['run_id']} to {history_file}")
    
    return history_file


def load_history(
    symbol: Optional[str] = None,
    limit: Optional[int] = None,
    history_dir: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Load optimization run history from history.jsonl.
    
    Args:
        symbol: If provided, filter to runs containing this symbol
        limit: If provided, return only the N most recent runs
        history_dir: If provided, use this directory instead of default
        
    Returns:
        List of run entries (newest first)
    """
    if history_dir is None:
        history_file = get_history_dir() / "history.jsonl"
    else:
        history_file = history_dir / "history.jsonl"
    
    if not history_file.exists():
        logger.debug(f"No history file found at {history_file}")
        return []
    
    entries = []
    
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = json.loads(line)
                    
                    # Filter by symbol if specified
                    if symbol:
                        # Check if any profile in this run matches the symbol
                        has_symbol = any(
                            p.get('symbol') == symbol
                            for p in entry.get('profiles', [])
                        )
                        if not has_symbol:
                            continue
                    
                    entries.append(entry)
                
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping invalid JSON line: {e}")
                    continue
    
    except Exception as e:
        logger.error(f"Error loading history: {e}")
        return []
    
    # Sort by created_at (newest first)
    entries.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    # Apply limit
    if limit is not None:
        entries = entries[:limit]
    
    return entries


def latest_profiles(
    symbol: str,
    max_runs: int = 20
) -> List[Dict[str, Any]]:
    """
    Get flattened list of per-symbol profile entries for a given symbol.
    
    Returns profile entries with run metadata attached, sorted newest→oldest.
    
    Args:
        symbol: Symbol to filter by
        max_runs: Maximum number of runs to examine
        
    Returns:
        List of profile dictionaries with run metadata
    """
    runs = load_history(symbol=symbol, limit=max_runs)
    
    profiles = []
    
    for run in runs:
        # Extract profiles for this symbol from this run
        for profile in run.get('profiles', []):
            if profile.get('symbol') == symbol:
                # Attach run metadata to profile
                profile_with_metadata = {
                    **profile,
                    'run_id': run.get('run_id'),
                    'run_created_at': run.get('created_at'),
                    'run_start': run.get('start'),
                    'run_end': run.get('end'),
                    'run_interval': run.get('interval'),
                    'trailing_stop_enabled': run.get('trailing_stop_enabled'),
                    'trailing_stop_pct': run.get('trailing_stop_pct')
                }
                profiles.append(profile_with_metadata)
    
    return profiles


def generate_run_id() -> str:
    """
    Generate a unique run ID.
    
    Returns:
        Unique run ID (timestamp + random suffix)
    """
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    suffix = uuid.uuid4().hex[:8]
    return f"{timestamp}_{suffix}"
