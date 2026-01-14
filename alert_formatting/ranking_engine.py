"""Signal ranking and sorting engine."""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

from trade_intelligence import TradeSignal, SignalDirection, RegimeType


class SortCriteria(str, Enum):
    """Sorting criteria for signals."""
    
    CONVICTION_DESC = "conviction_desc"  # Highest conviction first
    CONVICTION_ASC = "conviction_asc"    # Lowest conviction first
    AGREEMENT_DESC = "agreement_desc"     # Highest agreement first
    AGREEMENT_ASC = "agreement_asc"       # Lowest agreement first
    REGIME_TREND = "regime_trend"         # Trending signals first
    RISK_ASC = "risk_asc"                # Lowest risk first
    COMBINED = "combined"                 # Combined score (default)


@dataclass
class RankingConfig:
    """Configuration for signal ranking."""
    
    # Primary sort criteria
    primary_sort: SortCriteria = SortCriteria.COMBINED
    
    # Combined score weights (sum should be 1.0)
    conviction_weight: float = 0.5
    agreement_weight: float = 0.3
    regime_weight: float = 0.2
    
    # Regime preferences (higher = better)
    regime_scores: dict = None  # e.g. {'TRENDING': 1.0, 'BREAKOUT': 0.8, 'RANGING': 0.5}
    
    # Risk penalty (0-1, lower is better)
    risk_penalty_per_flag: float = 0.1
    
    # Filters
    min_conviction: Optional[float] = None  # Filter out signals with lower conviction
    direction_filter: Optional[SignalDirection] = None  # Filter by direction
    exclude_high_risk: bool = False  # Exclude signals with any risk flags
    
    def __post_init__(self):
        """Set defaults."""
        if self.regime_scores is None:
            self.regime_scores = {
                RegimeType.TRENDING: 1.0,
                RegimeType.BREAKOUT: 0.8,
                RegimeType.RANGING: 0.5,
                RegimeType.NEUTRAL: 0.3,
            }
        
        # Normalize regime scores to 0-1
        if self.regime_scores:
            max_score = max(self.regime_scores.values()) or 1.0
            self.regime_scores = {k: v / max_score for k, v in self.regime_scores.items()}


class RankingEngine:
    """Engine for ranking and sorting trade signals."""
    
    def __init__(self, config: Optional[RankingConfig] = None):
        """Initialize ranking engine.
        
        Args:
            config: Optional RankingConfig for customization
        """
        self.config = config or RankingConfig()
    
    def rank_signals(self, signals: List[TradeSignal]) -> List[TradeSignal]:
        """Rank signals according to configuration.
        
        Args:
            signals: List of TradeSignal objects
            
        Returns:
            Sorted list of TradeSignal objects (highest ranked first)
        """
        # Apply filters
        filtered = self._apply_filters(signals)
        
        # Sort based on primary criteria
        if self.config.primary_sort == SortCriteria.COMBINED:
            sorted_signals = sorted(
                filtered,
                key=lambda s: self._calculate_combined_score(s),
                reverse=True
            )
        elif self.config.primary_sort == SortCriteria.CONVICTION_DESC:
            sorted_signals = sorted(filtered, key=lambda s: s.conviction, reverse=True)
        elif self.config.primary_sort == SortCriteria.CONVICTION_ASC:
            sorted_signals = sorted(filtered, key=lambda s: s.conviction)
        elif self.config.primary_sort == SortCriteria.AGREEMENT_DESC:
            sorted_signals = sorted(filtered, key=lambda s: s.agreement_ratio, reverse=True)
        elif self.config.primary_sort == SortCriteria.AGREEMENT_ASC:
            sorted_signals = sorted(filtered, key=lambda s: s.agreement_ratio)
        elif self.config.primary_sort == SortCriteria.REGIME_TREND:
            sorted_signals = sorted(
                filtered,
                key=lambda s: self._get_regime_score(s.regime),
                reverse=True
            )
        elif self.config.primary_sort == SortCriteria.RISK_ASC:
            sorted_signals = sorted(
                filtered,
                key=lambda s: self._count_risk_flags(s)
            )
        else:
            sorted_signals = filtered
        
        return sorted_signals
    
    def get_top_signals(self, signals: List[TradeSignal], n: int = 5) -> List[TradeSignal]:
        """Get top N ranked signals.
        
        Args:
            signals: List of TradeSignal objects
            n: Number of top signals to return
            
        Returns:
            Top N ranked signals
        """
        ranked = self.rank_signals(signals)
        return ranked[:n]
    
    def group_by_direction(self, signals: List[TradeSignal]) -> dict:
        """Group signals by direction.
        
        Args:
            signals: List of TradeSignal objects
            
        Returns:
            Dict mapping SignalDirection to list of signals
        """
        groups = {
            SignalDirection.LONG: [],
            SignalDirection.SHORT: [],
            SignalDirection.FLAT: [],
        }
        
        ranked = self.rank_signals(signals)
        for signal in ranked:
            groups[signal.direction].append(signal)
        
        return groups
    
    def group_by_symbol(self, signals: List[TradeSignal]) -> dict:
        """Group signals by symbol.
        
        Args:
            signals: List of TradeSignal objects
            
        Returns:
            Dict mapping symbol to list of signals
        """
        groups = {}
        ranked = self.rank_signals(signals)
        for signal in ranked:
            if signal.symbol not in groups:
                groups[signal.symbol] = []
            groups[signal.symbol].append(signal)
        
        return groups
    
    def get_signal_summary(self, signals: List[TradeSignal]) -> dict:
        """Get summary statistics for signals.
        
        Args:
            signals: List of TradeSignal objects
            
        Returns:
            Summary dict with statistics
        """
        if not signals:
            return {
                "total": 0,
                "long_count": 0,
                "short_count": 0,
                "flat_count": 0,
                "avg_conviction": 0.0,
                "avg_agreement": 0.0,
                "high_conviction_count": 0,  # >= 0.7
                "high_risk_count": 0,  # Any risk flags
            }
        
        longs = [s for s in signals if s.direction == SignalDirection.LONG]
        shorts = [s for s in signals if s.direction == SignalDirection.SHORT]
        flats = [s for s in signals if s.direction == SignalDirection.FLAT]
        
        convictions = [s.conviction for s in signals]
        agreements = [s.agreement_ratio for s in signals]
        high_conviction = [s for s in signals if s.conviction >= 0.7]
        high_risk = [s for s in signals if self._count_risk_flags(s) > 0]
        
        return {
            "total": len(signals),
            "long_count": len(longs),
            "short_count": len(shorts),
            "flat_count": len(flats),
            "avg_conviction": sum(convictions) / len(convictions) if convictions else 0.0,
            "avg_agreement": sum(agreements) / len(agreements) if agreements else 0.0,
            "high_conviction_count": len(high_conviction),
            "high_risk_count": len(high_risk),
        }
    
    # ========== Private helper methods ==========
    
    def _apply_filters(self, signals: List[TradeSignal]) -> List[TradeSignal]:
        """Apply configured filters to signals.
        
        Args:
            signals: List of TradeSignal objects
            
        Returns:
            Filtered list
        """
        filtered = signals
        
        # Min conviction filter
        if self.config.min_conviction is not None:
            filtered = [s for s in filtered if s.conviction >= self.config.min_conviction]
        
        # Direction filter
        if self.config.direction_filter is not None:
            filtered = [s for s in filtered if s.direction == self.config.direction_filter]
        
        # High risk filter
        if self.config.exclude_high_risk:
            filtered = [s for s in filtered if self._count_risk_flags(s) == 0]
        
        return filtered
    
    def _calculate_combined_score(self, signal: TradeSignal) -> float:
        """Calculate combined ranking score for a signal.
        
        Args:
            signal: TradeSignal to score
            
        Returns:
            Combined score (0-1)
        """
        # Component scores
        conviction_score = signal.conviction
        agreement_score = signal.agreement_ratio
        regime_score = self._get_regime_score(signal.regime)
        
        # Risk penalty
        risk_flags_count = self._count_risk_flags(signal)
        risk_penalty = risk_flags_count * self.config.risk_penalty_per_flag
        
        # Combined weighted score
        combined = (
            self.config.conviction_weight * conviction_score +
            self.config.agreement_weight * agreement_score +
            self.config.regime_weight * regime_score
        )
        
        # Apply risk penalty
        combined = max(0.0, combined - risk_penalty)
        
        return min(1.0, combined)  # Clamp to 0-1
    
    def _get_regime_score(self, regime: RegimeType) -> float:
        """Get score for a regime type.
        
        Args:
            regime: RegimeType to score
            
        Returns:
            Score (0-1)
        """
        return self.config.regime_scores.get(regime, 0.5)
    
    def _count_risk_flags(self, signal: TradeSignal) -> int:
        """Count number of active risk flags.
        
        Args:
            signal: TradeSignal to evaluate
            
        Returns:
            Number of active risk flags
        """
        count = 0
        if signal.risk_flags.volatility_spike:
            count += 1
        if signal.risk_flags.low_liquidity:
            count += 1
        if signal.risk_flags.drawdown_risk:
            count += 1
        if signal.risk_flags.conflicting_signals:
            count += 1
        return count
