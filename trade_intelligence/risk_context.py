"""
Risk Context Analysis

Detects and flags risk factors that should influence signal confidence:
- Volatility spikes
- Low liquidity proxies
- Portfolio drawdown
- Conflicting signals
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskContext:
    """Risk context snapshot."""
    volatility_spike: bool = False
    low_liquidity: bool = False
    drawdown_risk: bool = False
    conflicting_signals: bool = False


class RiskContextAnalyzer:
    """Detect risk flags from market conditions."""
    
    def __init__(
        self,
        vol_spike_threshold: float = 1.5,      # Vol spike = current / 20-period MA > 1.5
        drawdown_threshold: float = 0.10,      # >10% drawdown = risk
    ):
        """
        Initialize risk analyzer.
        
        Args:
            vol_spike_threshold: Volatility spike multiplier
            drawdown_threshold: Drawdown threshold (e.g., 0.10 = 10%)
        """
        self.vol_spike_threshold = vol_spike_threshold
        self.drawdown_threshold = drawdown_threshold
    
    def detect_volatility_spike(
        self,
        current_volatility: Optional[float],
        volatility_sma: Optional[float],
    ) -> bool:
        """
        Detect if volatility has spiked.
        
        Args:
            current_volatility: Current ATR or std dev
            volatility_sma: 20-period SMA of volatility
        
        Returns:
            True if spike detected
        """
        if current_volatility is None or volatility_sma is None:
            return False
        
        if volatility_sma <= 0:
            return False
        
        ratio = current_volatility / volatility_sma
        return ratio > self.vol_spike_threshold
    
    def detect_low_liquidity(
        self,
        volume: Optional[float],
        volume_sma: Optional[float],
    ) -> bool:
        """
        Detect low liquidity proxy (volume drying up).
        
        Args:
            volume: Current candle volume
            volume_sma: 20-period volume SMA
        
        Returns:
            True if volume suspiciously low
        """
        if volume is None or volume_sma is None:
            return False
        
        if volume_sma <= 0:
            return False
        
        # Volume < 50% of average = potential liquidity issue
        ratio = volume / volume_sma
        return ratio < 0.5
    
    def detect_drawdown_risk(
        self,
        current_equity: Optional[float],
        peak_equity: Optional[float],
    ) -> bool:
        """
        Detect if portfolio drawdown is elevated.
        
        Args:
            current_equity: Current portfolio value
            peak_equity: Peak equity since trade session start
        
        Returns:
            True if drawdown exceeds threshold
        """
        if current_equity is None or peak_equity is None:
            return False
        
        if peak_equity <= 0:
            return False
        
        drawdown = (peak_equity - current_equity) / peak_equity
        return drawdown > self.drawdown_threshold
    
    def detect_conflicting_signals(
        self,
        num_strategies: int,
        agreeing_count: int,
    ) -> bool:
        """
        Detect if strategies are in conflict.
        
        Args:
            num_strategies: Total strategies
            agreeing_count: Strategies in agreement
        
        Returns:
            True if disagreement is significant (>30% dissent)
        """
        if num_strategies < 2:
            return False
        
        agreement_ratio = agreeing_count / num_strategies
        dissent_ratio = 1.0 - agreement_ratio
        
        return dissent_ratio > 0.30
    
    def analyze(
        self,
        current_volatility: Optional[float] = None,
        volatility_sma: Optional[float] = None,
        volume: Optional[float] = None,
        volume_sma: Optional[float] = None,
        current_equity: Optional[float] = None,
        peak_equity: Optional[float] = None,
        num_strategies: Optional[int] = None,
        agreeing_count: Optional[int] = None,
    ) -> RiskContext:
        """
        Comprehensive risk analysis.
        
        Args:
            current_volatility: Current volatility measure
            volatility_sma: Volatility SMA
            volume: Current volume
            volume_sma: Volume SMA
            current_equity: Current portfolio equity
            peak_equity: Peak equity
            num_strategies: Number of strategies
            agreeing_count: Agreeing strategies
        
        Returns:
            RiskContext with all flags
        """
        return RiskContext(
            volatility_spike=self.detect_volatility_spike(
                current_volatility, volatility_sma
            ),
            low_liquidity=self.detect_low_liquidity(volume, volume_sma),
            drawdown_risk=self.detect_drawdown_risk(current_equity, peak_equity),
            conflicting_signals=(
                self.detect_conflicting_signals(num_strategies, agreeing_count)
                if num_strategies is not None and agreeing_count is not None
                else False
            ),
        )
