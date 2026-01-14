"""
Backtests Module

Configuration-driven historical backtesting that reuses live trading components.
"""

from .config_backtest import run_config_backtest

__all__ = ["run_config_backtest"]
