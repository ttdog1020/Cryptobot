"""
Validation and Safety System (Module 20)

This package provides a "paranoia layer" for detecting accounting, risk,
and execution discrepancies before enabling real trading.

Components:
- invariants: Reusable invariant check functions for accounting/risk/position validation
- synthetic_data: Deterministic synthetic OHLCV data generators for testing
- safety_suite: Comprehensive safety test suite with differential testing
"""

from .invariants import (
    check_accounting_invariants,
    check_risk_invariants,
    check_position_invariants
)

from .synthetic_data import (
    generate_trend_series,
    generate_range_series,
    generate_spike_series
)

from .safety_suite import (
    run_backtest_vs_paper_consistency_test,
    run_safety_suite
)

__all__ = [
    # Invariants
    'check_accounting_invariants',
    'check_risk_invariants',
    'check_position_invariants',
    
    # Synthetic data
    'generate_trend_series',
    'generate_range_series',
    'generate_spike_series',
    
    # Safety suite
    'run_backtest_vs_paper_consistency_test',
    'run_safety_suite'
]
