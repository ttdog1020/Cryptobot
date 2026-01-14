"""
Trade Intelligence Module

Provides analysis-only trade signal generation and aggregation without execution.
Converts strategy outputs into structured, explainable trade signals with
confidence scoring and risk context.

Key Components:
- signal_model: TradeSignal data structure
- signal_engine: Core aggregation engine
- confidence: Conviction scoring logic
- risk_context: Risk context detection
- aggregation: Multi-strategy signal combination

Usage:
    from trade_intelligence import TradeSignal, SignalEngine
    
    engine = SignalEngine()
    signal = engine.aggregate_signals(
        strategies_signals=[...],
        symbol='BTCUSDT',
        timeframe='1h'
    )
    # signal is JSON-serializable
    print(signal.to_dict())
"""

from .signal_model import TradeSignal, SignalDirection, SignalConfidence
from .signal_engine import SignalEngine
from .confidence import ConfidenceCalculator
from .risk_context import RiskContextAnalyzer

__all__ = [
    'TradeSignal',
    'SignalDirection',
    'SignalConfidence',
    'SignalEngine',
    'ConfidenceCalculator',
    'RiskContextAnalyzer',
]
