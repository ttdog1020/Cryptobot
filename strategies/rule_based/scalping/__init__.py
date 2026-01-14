"""
Scalping strategies optimized for 1m-5m timeframes.
"""

from .scalping_ema_rsi import ScalpingEMARSI, generate_signal, add_indicators

__all__ = ["ScalpingEMARSI", "generate_signal", "add_indicators"]
