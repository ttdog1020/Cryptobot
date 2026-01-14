"""Signal formatting logic for converting TradeSignal to text/markdown."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import json

from trade_intelligence import TradeSignal, SignalConfidence, SignalDirection


@dataclass
class FormatterConfig:
    """Configuration for alert formatting."""
    
    # Direction display
    direction_symbols: dict = None  # e.g. {'LONG': '🟢', 'SHORT': '🔴', 'FLAT': '⚪'}
    
    # Confidence display
    confidence_symbols: dict = None  # e.g. {'VERY_HIGH': '█████', 'HIGH': '████', ...}
    
    # Include fields
    include_metadata: bool = True
    include_risk_flags: bool = True
    include_strategy_names: bool = True
    include_timestamp: bool = True
    
    # Decimal precision
    decimal_places: int = 3
    
    # Line width for text wrapping
    line_width: int = 100
    
    def __post_init__(self):
        """Set defaults if not provided."""
        if self.direction_symbols is None:
            self.direction_symbols = {
                "LONG": "BUY",
                "SHORT": "SELL",
                "FLAT": "HOLD"
            }
        
        if self.confidence_symbols is None:
            self.confidence_symbols = {
                "VERY_HIGH": "█████",
                "HIGH": "████ ",
                "MEDIUM": "███  ",
                "LOW": "██   ",
                "VERY_LOW": "█    "
            }


class AlertFormatter(ABC):
    """Base class for alert formatters."""
    
    def __init__(self, config: Optional[FormatterConfig] = None):
        """Initialize formatter with optional configuration."""
        self.config = config or FormatterConfig()
    
    @abstractmethod
    def format_signal(self, signal: TradeSignal) -> str:
        """Format a single trade signal.
        
        Args:
            signal: TradeSignal to format
            
        Returns:
            Formatted string representation
        """
        pass
    
    @abstractmethod
    def format_signals(self, signals: list[TradeSignal]) -> str:
        """Format multiple trade signals.
        
        Args:
            signals: List of TradeSignal objects
            
        Returns:
            Formatted string representation
        """
        pass
    
    def _format_conviction(self, conviction: float) -> str:
        """Format conviction score with symbol.
        
        Args:
            conviction: Conviction score (0-1)
            
        Returns:
            Formatted string with symbol
        """
        # Map to confidence category
        if conviction >= 0.8:
            symbol = self.config.confidence_symbols["VERY_HIGH"]
            label = "VERY_HIGH"
        elif conviction >= 0.6:
            symbol = self.config.confidence_symbols["HIGH"]
            label = "HIGH"
        elif conviction >= 0.4:
            symbol = self.config.confidence_symbols["MEDIUM"]
            label = "MEDIUM"
        elif conviction >= 0.2:
            symbol = self.config.confidence_symbols["LOW"]
            label = "LOW"
        else:
            symbol = self.config.confidence_symbols["VERY_LOW"]
            label = "VERY_LOW"
        
        conviction_rounded = round(conviction, self.config.decimal_places)
        return f"{symbol} {conviction_rounded} ({label})"
    
    def _format_risk_flags(self, signal: TradeSignal) -> str:
        """Format risk flags as human-readable string.
        
        Args:
            signal: TradeSignal with risk flags
            
        Returns:
            Risk flags description
        """
        if not self.config.include_risk_flags:
            return ""
        
        flags = []
        if signal.risk_flags.volatility_spike:
            flags.append("⚡ Vol Spike")
        if signal.risk_flags.low_liquidity:
            flags.append("💧 Low Liquidity")
        if signal.risk_flags.drawdown_risk:
            flags.append("📉 Drawdown Risk")
        if signal.risk_flags.conflicting_signals:
            flags.append("⚠️ Conflicting")
        
        return " | ".join(flags) if flags else "No Risks Detected"
    
    def _format_agreement(self, signal: TradeSignal) -> str:
        """Format agreement metrics.
        
        Args:
            signal: TradeSignal with agreement data
            
        Returns:
            Agreement description
        """
        agreement_pct = round(signal.agreement_ratio * 100, self.config.decimal_places)
        return f"{signal.num_strategies} strategies, {agreement_pct}% agreement"


class TextAlertFormatter(AlertFormatter):
    """Plain text formatter for trade signals."""
    
    def format_signal(self, signal: TradeSignal) -> str:
        """Format signal as plain text.
        
        Args:
            signal: TradeSignal to format
            
        Returns:
            Plain text representation
        """
        lines = []
        
        # Header
        direction = self.config.direction_symbols[signal.direction.value]
        lines.append(f"{'='*60}")
        lines.append(f"{direction.upper()} SIGNAL: {signal.symbol} ({signal.timeframe})")
        lines.append(f"{'='*60}")
        
        # Core signal info
        lines.append(f"Direction: {signal.direction.value}")
        lines.append(f"Conviction: {self._format_conviction(signal.conviction)}")
        lines.append(f"Regime: {signal.regime.value}")
        lines.append(f"Agreement: {self._format_agreement(signal)}")
        
        # Risk flags
        lines.append(f"Risk Status: {self._format_risk_flags(signal)}")
        
        # Strategy details
        if self.config.include_strategy_names and signal.strategy_names:
            lines.append(f"Strategies: {', '.join(signal.strategy_names)}")
        
        # Timestamp
        if self.config.include_timestamp:
            lines.append(f"Signal Time: {signal.timestamp}")
        
        # Metadata
        if self.config.include_metadata and signal.metadata:
            lines.append(f"Rationale: {signal.metadata.get('rationale', 'N/A')}")
        
        lines.append(f"{'='*60}")
        
        return "\n".join(lines)
    
    def format_signals(self, signals: list[TradeSignal]) -> str:
        """Format multiple signals as plain text.
        
        Args:
            signals: List of TradeSignal objects
            
        Returns:
            Plain text with all signals
        """
        if not signals:
            return "No signals to display."
        
        formatted = []
        for i, signal in enumerate(signals, 1):
            formatted.append(f"\n[{i}/{len(signals)}]")
            formatted.append(self.format_signal(signal))
        
        return "\n".join(formatted)


class MarkdownAlertFormatter(AlertFormatter):
    """Markdown formatter for trade signals."""
    
    def format_signal(self, signal: TradeSignal) -> str:
        """Format signal as markdown.
        
        Args:
            signal: TradeSignal to format
            
        Returns:
            Markdown representation
        """
        lines = []
        
        # Header
        direction_emoji = {"LONG": "📈", "SHORT": "📉", "FLAT": "➡️"}
        direction = self.config.direction_symbols[signal.direction.value]
        lines.append(f"## {direction_emoji.get(signal.direction.value, '📊')} {direction.upper()} - {signal.symbol}/{signal.timeframe}")
        
        # Core metrics
        lines.append(f"**Conviction:** {self._format_conviction(signal.conviction)}")
        lines.append(f"**Regime:** `{signal.regime.value}`")
        lines.append(f"**Agreement:** {self._format_agreement(signal)}")
        
        # Risk flags
        lines.append(f"**Risk Status:** {self._format_risk_flags(signal)}")
        
        # Strategy details
        if self.config.include_strategy_names and signal.strategy_names:
            lines.append(f"**Strategies:** `{', '.join(signal.strategy_names)}`")
        
        # Metadata
        if self.config.include_metadata and signal.metadata:
            rationale = signal.metadata.get('rationale', 'N/A')
            lines.append(f"> {rationale}")
        
        # Timestamp
        if self.config.include_timestamp:
            lines.append(f"*{signal.timestamp}*")
        
        return "\n".join(lines)
    
    def format_signals(self, signals: list[TradeSignal]) -> str:
        """Format multiple signals as markdown.
        
        Args:
            signals: List of TradeSignal objects
            
        Returns:
            Markdown with all signals
        """
        if not signals:
            return "No signals to display."
        
        lines = []
        lines.append("# Trade Signals Report")
        lines.append(f"*Generated: {signals[0].timestamp if signals else 'N/A'}*")
        lines.append("")
        
        for signal in signals:
            lines.append(self.format_signal(signal))
            lines.append("---")
        
        return "\n".join(lines)
