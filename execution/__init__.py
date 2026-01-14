"""
MODULE 18 + 24: Execution Engine

Order execution layer with paper trading support and safety monitoring.

MODULE 24: Added safety monitoring, BinanceClient stub, and multi-mode support.
"""

from .order_types import (
    OrderSide,
    OrderType,
    OrderStatus,
    OrderRequest,
    OrderFill,
    ExecutionResult,
    Position
)
from .paper_trader import PaperTrader
from .execution_engine import ExecutionEngine
from .exchange_client_base import ExchangeClientBase
from .binance_client import BinanceClient, create_binance_client
from .safety import SafetyMonitor, SafetyLimits, SafetyViolation

__all__ = [
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'OrderRequest',
    'OrderFill',
    'ExecutionResult',
    'Position',
    'PaperTrader',
    'ExecutionEngine',
    'ExchangeClientBase',
    'BinanceClient',
    'create_binance_client',
    'SafetyMonitor',
    'SafetyLimits',
    'SafetyViolation'
]
