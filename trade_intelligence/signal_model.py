"""
Trade Signal Data Model

Defines the core TradeSignal structure: JSON-serializable representation
of an aggregated trade signal with confidence, context, and metadata.
"""

from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class SignalDirection(str, Enum):
    """Trade signal direction."""
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class SignalConfidence(str, Enum):
    """Confidence level categorization."""
    VERY_HIGH = "VERY_HIGH"  # 0.8-1.0
    HIGH = "HIGH"             # 0.6-0.8
    MEDIUM = "MEDIUM"         # 0.4-0.6
    LOW = "LOW"               # 0.2-0.4
    VERY_LOW = "VERY_LOW"     # 0.0-0.2


class RegimeType(str, Enum):
    """Market regime classification."""
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    BREAKOUT = "BREAKOUT"
    NEUTRAL = "NEUTRAL"


@dataclass
class RiskFlags:
    """Risk context flags."""
    volatility_spike: bool = False      # Recent volatility increase
    low_liquidity: bool = False         # Potential liquidity issues
    drawdown_risk: bool = False         # Portfolio drawdown elevated
    conflicting_signals: bool = False   # Strategies disagreeing
    
    def to_dict(self) -> Dict[str, bool]:
        """Export to dictionary."""
        return asdict(self)


@dataclass
class TradeSignal:
    """
    Aggregated trade signal with confidence and context.
    
    Attributes:
        direction: Trade direction (LONG/SHORT/FLAT)
        conviction: Confidence score 0.0-1.0
        confidence_category: High-level confidence (VERY_HIGH/HIGH/MEDIUM/LOW/VERY_LOW)
        symbol: Trading pair (e.g., BTCUSDT)
        timeframe: Candle timeframe (e.g., 1h, 4h)
        regime: Market regime (TRENDING/RANGING/BREAKOUT/NEUTRAL)
        timestamp: When signal was generated
        
        # Strategy agreement
        num_strategies: Number of strategies providing input
        agreeing_strategies: Count of agreeing strategies
        agreement_ratio: Fraction of strategies agreeing (0.0-1.0)
        
        # Risk context
        risk_flags: Risk context indicators
        
        # Metadata
        strategy_names: Which strategies contributed
        volatility_percentile: Current volatility percentile (0-100)
        tags: Free-form tags (e.g., ["breakout", "confluence"])
        rationale: Human-readable explanation of signal
        metadata: Additional context for debugging
    """
    
    # Core signal
    direction: SignalDirection
    conviction: float  # 0.0-1.0
    symbol: str
    timeframe: str
    
    # Derived
    confidence_category: SignalConfidence = field(init=False)
    regime: RegimeType = RegimeType.NEUTRAL
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Strategy agreement
    num_strategies: int = 1
    agreeing_strategies: int = 1
    agreement_ratio: float = 1.0
    
    # Risk
    risk_flags: RiskFlags = field(default_factory=RiskFlags)
    
    # Metadata
    strategy_names: List[str] = field(default_factory=list)
    volatility_percentile: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    rationale: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Compute confidence category from conviction score."""
        if self.conviction >= 0.8:
            self.confidence_category = SignalConfidence.VERY_HIGH
        elif self.conviction >= 0.6:
            self.confidence_category = SignalConfidence.HIGH
        elif self.conviction >= 0.4:
            self.confidence_category = SignalConfidence.MEDIUM
        elif self.conviction >= 0.2:
            self.confidence_category = SignalConfidence.LOW
        else:
            self.confidence_category = SignalConfidence.VERY_LOW
    
    def to_dict(self) -> Dict[str, Any]:
        """Export to JSON-serializable dictionary."""
        return {
            'direction': self.direction.value,
            'conviction': round(self.conviction, 3),
            'confidence_category': self.confidence_category.value,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'regime': self.regime.value,
            'timestamp': self.timestamp,
            'strategy_agreement': {
                'num_strategies': self.num_strategies,
                'agreeing': self.agreeing_strategies,
                'agreement_ratio': round(self.agreement_ratio, 3),
            },
            'risk_context': {
                'flags': self.risk_flags.to_dict(),
                'volatility_percentile': self.volatility_percentile,
            },
            'metadata': {
                'strategies': self.strategy_names,
                'tags': self.tags,
                'rationale': self.rationale,
                'context': self.metadata,
            }
        }
    
    def is_actionable(self, min_conviction: float = 0.5) -> bool:
        """Check if signal meets minimum conviction threshold."""
        return self.conviction >= min_conviction and self.direction != SignalDirection.FLAT
    
    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"TradeSignal({self.symbol} {self.timeframe} @ {self.timestamp}): "
            f"{self.direction.value} conviction={self.conviction:.2f} "
            f"({self.confidence_category.value}) "
            f"regime={self.regime.value} "
            f"agreement={self.agreement_ratio:.1%}"
        )
