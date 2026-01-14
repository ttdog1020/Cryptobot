"""
MODULE 30: Strategy Auto-Optimizer v1

Offline self-training optimizer that sweeps parameter combinations
and ranks strategies by performance.

Phase 1: Read-only recommendations (no auto-config updates).
"""

from .param_search import (
    OptimizationRunConfig,
    iter_param_combinations,
    run_param_search
)

__all__ = [
    'OptimizationRunConfig',
    'iter_param_combinations',
    'run_param_search'
]
