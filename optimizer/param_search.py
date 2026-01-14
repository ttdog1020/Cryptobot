"""
MODULE 30: Parameter Search Engine

Grid search optimizer for strategy parameters using backtests.config_backtest runner.

Features:
- Parameter grid definition and iteration
- Temporary config override (no modification of live configs)
- Performance evaluation using analytics.paper_report
- Ranked results by total return %

Usage:
    from optimizer.param_search import run_param_search, OptimizationRunConfig
    from datetime import datetime
    
    config = OptimizationRunConfig(
        symbols=["BTCUSDT"],
        start=datetime(2025, 11, 1),
        end=datetime(2025, 12, 1),
        interval="1m",
        param_grid={
            "ema_fast": [5, 8, 12],
            "ema_slow": [21, 26, 34],
            "rsi_overbought": [70, 75],
        }
    )
    
    results = run_param_search(config)
    for result in results[:5]:  # Top 5
        print(f"Score: {result['score']:.2f}% - Params: {result['params']}")
"""

import logging
import sys
import yaml
import json
import itertools
from pathlib import Path
from typing import Dict, Any, List, Optional, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from tempfile import NamedTemporaryFile

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtests.config_backtest import run_config_backtest
from analytics.paper_report import PaperTradeReport

logger = logging.getLogger(__name__)


@dataclass
class OptimizationRunConfig:
    """
    Configuration for parameter optimization run.
    
    Attributes:
        symbols: List of symbols to backtest
        start: Backtest start date
        end: Backtest end date
        interval: Candle interval (e.g., "1m", "5m")
        param_grid: Parameter grid as dict of param_name -> list of values
        max_runs: Optional limit on number of parameter combinations to test
        label: Label for this optimization run (used in output files)
        base_config_path: Path to base configuration file
    """
    symbols: List[str]
    start: datetime
    end: datetime
    interval: str = "1m"
    param_grid: Dict[str, List[Any]] = field(default_factory=dict)
    max_runs: Optional[int] = None
    label: str = "scalping_ema_rsi_opt"
    base_config_path: str = "config/live.yaml"


def iter_param_combinations(param_grid: Dict[str, List[Any]]) -> Iterable[Dict[str, Any]]:
    """
    Generate all combinations from parameter grid.
    
    Uses itertools.product for Cartesian product of parameter values.
    
    Args:
        param_grid: Dictionary of parameter_name -> [value1, value2, ...]
        
    Yields:
        Dictionary of parameter_name -> value for each combination
        
    Example:
        >>> grid = {"fast": [5, 8], "slow": [21, 26]}
        >>> list(iter_param_combinations(grid))
        [
            {"fast": 5, "slow": 21},
            {"fast": 5, "slow": 26},
            {"fast": 8, "slow": 21},
            {"fast": 8, "slow": 26}
        ]
    """
    if not param_grid:
        yield {}
        return
    
    # Extract keys and values
    keys = list(param_grid.keys())
    values = [param_grid[k] for k in keys]
    
    # Generate Cartesian product
    for combination in itertools.product(*values):
        yield dict(zip(keys, combination))


def _create_temp_config(
    base_config_path: str,
    param_override: Dict[str, Any]
) -> Path:
    """
    Create temporary config file with parameter overrides.
    
    Args:
        base_config_path: Path to base configuration
        param_override: Parameters to override in strategy.params section
        
    Returns:
        Path to temporary configuration file
    """
    # Load base config
    with open(base_config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Override strategy parameters
    if "strategy" not in config:
        config["strategy"] = {}
    if "params" not in config["strategy"]:
        config["strategy"]["params"] = {}
    
    # Handle case where params is None (YAML with all commented values)
    if config["strategy"]["params"] is None:
        config["strategy"]["params"] = {}
    
    # Apply parameter overrides
    config["strategy"]["params"].update(param_override)
    
    # Create temporary file
    temp_file = NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml.dump(config, temp_file, default_flow_style=False)
    temp_file.close()
    
    return Path(temp_file.name)


def _compute_metrics_from_log(log_path: Path) -> Dict[str, Any]:
    """
    Compute performance metrics from backtest log CSV.
    
    Args:
        log_path: Path to trade log CSV
        
    Returns:
        Dictionary with performance metrics
    """
    try:
        report = PaperTradeReport(log_path)
        metrics = report.get_overall_metrics()
        
        return {
            'total_return_pct': metrics['total_pnl_pct'],
            'total_pnl': metrics['total_pnl'],
            'total_trades': metrics['total_trades'],
            'win_rate': metrics['win_rate'],
            'max_drawdown_pct': metrics['max_drawdown_pct'],
            'avg_trade_pnl': metrics['avg_trade_pnl'],
            'largest_win': metrics['largest_win'],
            'largest_loss': metrics['largest_loss']
        }
    except Exception as e:
        logger.error(f"Error computing metrics from {log_path}: {e}")
        return {
            'total_return_pct': 0.0,
            'total_pnl': 0.0,
            'total_trades': 0,
            'win_rate': 0.0,
            'max_drawdown_pct': 0.0,
            'avg_trade_pnl': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0
        }


def run_param_search(cfg: OptimizationRunConfig) -> List[Dict[str, Any]]:
    """
    Run parameter search optimization.
    
    For each parameter combination:
    1. Create temporary config with parameter override
    2. Run backtest using run_config_backtest
    3. Compute metrics from trade log CSV
    4. Collect results
    
    Args:
        cfg: Optimization configuration
        
    Returns:
        List of result dictionaries, sorted by score (total_return_pct) descending.
        Each result contains:
        - params: Parameter combination
        - score: Primary score (total return %)
        - metrics: Full performance metrics
        - symbols: List of symbols tested
    """
    logger.info("="*70)
    logger.info("PARAMETER SEARCH OPTIMIZATION")
    logger.info("="*70)
    logger.info(f"Label: {cfg.label}")
    logger.info(f"Symbols: {cfg.symbols}")
    logger.info(f"Date range: {cfg.start.strftime('%Y-%m-%d')} to {cfg.end.strftime('%Y-%m-%d')}")
    logger.info(f"Interval: {cfg.interval}")
    logger.info(f"Parameter grid: {cfg.param_grid}")
    
    # Generate parameter combinations
    combinations = list(iter_param_combinations(cfg.param_grid))
    total_combinations = len(combinations)
    
    # Apply max_runs limit
    if cfg.max_runs and cfg.max_runs < total_combinations:
        logger.info(f"Limiting to {cfg.max_runs} runs (out of {total_combinations} total combinations)")
        combinations = combinations[:cfg.max_runs]
    else:
        logger.info(f"Total combinations to test: {total_combinations}")
    
    logger.info("="*70)
    
    results = []
    temp_files = []  # Track temp files for cleanup
    
    try:
        for i, params in enumerate(combinations, 1):
            logger.info(f"\n[{i}/{len(combinations)}] Testing parameters: {params}")
            
            # Create temporary config
            temp_config_path = _create_temp_config(cfg.base_config_path, params)
            temp_files.append(temp_config_path)
            
            # Generate unique log suffix
            log_suffix = f"opt_{cfg.label}_{i:03d}"
            
            try:
                # Run backtest
                log_path = run_config_backtest(
                    start=cfg.start.strftime("%Y-%m-%d"),
                    end=cfg.end.strftime("%Y-%m-%d"),
                    interval=cfg.interval,
                    config_path=str(temp_config_path),
                    symbols=cfg.symbols,
                    log_suffix=log_suffix
                )
                
                # Compute metrics
                metrics = _compute_metrics_from_log(log_path)
                
                # Store result
                result = {
                    'params': params,
                    'score': metrics['total_return_pct'],
                    'metrics': metrics,
                    'symbols': cfg.symbols,
                    'log_file': str(log_path)
                }
                
                results.append(result)
                
                logger.info(f"  → Score: {result['score']:+.2f}% | "
                          f"Trades: {metrics['total_trades']} | "
                          f"Win Rate: {metrics['win_rate']:.1f}%")
                
            except Exception as e:
                logger.error(f"  → ERROR: {e}")
                # Store failed result with zero score
                results.append({
                    'params': params,
                    'score': 0.0,
                    'metrics': {
                        'total_return_pct': 0.0,
                        'error': str(e)
                    },
                    'symbols': cfg.symbols,
                    'log_file': None
                })
    
    finally:
        # Cleanup temporary config files
        for temp_file in temp_files:
            try:
                temp_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_file}: {e}")
    
    # Sort by score (descending)
    results.sort(key=lambda x: x['score'], reverse=True)
    
    logger.info("\n" + "="*70)
    logger.info("OPTIMIZATION COMPLETE")
    logger.info("="*70)
    logger.info(f"Total runs: {len(results)}")
    logger.info(f"Best score: {results[0]['score']:+.2f}%")
    logger.info(f"Worst score: {results[-1]['score']:+.2f}%")
    logger.info("="*70)
    
    return results
