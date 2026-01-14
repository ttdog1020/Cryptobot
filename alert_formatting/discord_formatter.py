"""Discord-specific alert formatting with rich embeds and mentions."""

from dataclasses import dataclass
from typing import Optional
import json

from trade_intelligence import TradeSignal, SignalDirection, SignalConfidence

from .signal_formatter import AlertFormatter, FormatterConfig


@dataclass
class DiscordConfig(FormatterConfig):
    """Discord-specific formatting configuration."""
    
    # Embed colors (RGB hex)
    color_long: int = 0x00FF00  # Green
    color_short: int = 0xFF0000  # Red
    color_flat: int = 0x808080  # Gray
    
    # Mentions (e.g., "<@USER_ID>" or "<@&ROLE_ID>")
    mention_on_long: Optional[str] = None
    mention_on_short: Optional[str] = None
    mention_on_high_conviction: Optional[str] = None  # conviction >= 0.7
    
    # Formatting options
    use_embeds: bool = True
    include_footer: bool = True
    include_thumbnail: bool = True
    
    # Thresholds for alerts
    conviction_threshold_alert: float = 0.6  # Only alert if >= this
    
    def __post_init__(self):
        """Set Discord defaults."""
        super().__post_init__()
        if self.direction_symbols is None or self.direction_symbols == {"LONG": "BUY", "SHORT": "SELL", "FLAT": "HOLD"}:
            self.direction_symbols = {
                "LONG": "🟢 LONG",
                "SHORT": "🔴 SHORT",
                "FLAT": "⚪ FLAT"
            }


class DiscordAlertFormatter(AlertFormatter):
    """Discord-specific formatter for rich embeds and messages."""
    
    def __init__(self, config: Optional[DiscordConfig] = None):
        """Initialize Discord formatter."""
        self.config = config or DiscordConfig()
    
    def format_signal(self, signal: TradeSignal) -> str:
        """Format signal as Discord message (plain text for fallback).
        
        Args:
            signal: TradeSignal to format
            
        Returns:
            Discord message (plain text version)
        """
        # Check conviction threshold
        if signal.conviction < self.config.conviction_threshold_alert:
            return f"Signal conviction {signal.conviction:.3f} below alert threshold ({self.config.conviction_threshold_alert})"
        
        # Build mentions
        mentions = []
        if signal.direction == SignalDirection.LONG and self.config.mention_on_long:
            mentions.append(self.config.mention_on_long)
        elif signal.direction == SignalDirection.SHORT and self.config.mention_on_short:
            mentions.append(self.config.mention_on_short)
        
        if signal.conviction >= 0.7 and self.config.mention_on_high_conviction:
            mentions.append(self.config.mention_on_high_conviction)
        
        mention_str = " ".join(mentions) if mentions else ""
        
        # Build message
        direction = self.config.direction_symbols[signal.direction.value]
        conviction_str = self._format_conviction(signal.conviction)
        risk_str = self._format_risk_flags(signal)
        
        message = f"{mention_str}\n"
        message += f"**{direction}** {signal.symbol}/{signal.timeframe}\n"
        message += f"Conviction: {conviction_str}\n"
        message += f"Regime: {signal.regime.value}\n"
        message += f"Risk: {risk_str}"
        
        return message
    
    def format_signals(self, signals: list[TradeSignal]) -> str:
        """Format multiple signals for Discord.
        
        Args:
            signals: List of TradeSignal objects
            
        Returns:
            Discord message with formatted signals
        """
        if not signals:
            return "No signals to display."
        
        # Filter by conviction threshold
        filtered = [s for s in signals if s.conviction >= self.config.conviction_threshold_alert]
        if not filtered:
            return f"No signals meet conviction threshold ({self.config.conviction_threshold_alert})"
        
        lines = []
        lines.append("📊 **Trade Signals Update**")
        lines.append("")
        
        for signal in filtered:
            lines.append(self.format_signal(signal))
            lines.append("")
        
        return "\n".join(lines)
    
    def format_as_embed(self, signal: TradeSignal) -> dict:
        """Format signal as Discord embed JSON.
        
        Args:
            signal: TradeSignal to format
            
        Returns:
            Discord embed dict (for use with discord.py or similar)
        """
        # Determine color based on direction
        color_map = {
            SignalDirection.LONG: self.config.color_long,
            SignalDirection.SHORT: self.config.color_short,
            SignalDirection.FLAT: self.config.color_flat,
        }
        color = color_map.get(signal.direction, self.config.color_flat)
        
        # Build fields
        fields = [
            {
                "name": "Conviction",
                "value": self._format_conviction(signal.conviction),
                "inline": True
            },
            {
                "name": "Regime",
                "value": signal.regime.value,
                "inline": True
            },
            {
                "name": "Agreement",
                "value": self._format_agreement(signal),
                "inline": False
            },
            {
                "name": "Risk Status",
                "value": self._format_risk_flags(signal),
                "inline": False
            }
        ]
        
        # Add strategy names if configured
        if self.config.include_strategy_names and signal.strategy_names:
            fields.append({
                "name": "Strategies",
                "value": ", ".join(signal.strategy_names),
                "inline": False
            })
        
        # Add rationale if available
        if self.config.include_metadata and signal.metadata:
            rationale = signal.metadata.get('rationale', '')
            if rationale:
                fields.append({
                    "name": "Rationale",
                    "value": rationale[:1024],  # Discord limit 1024 chars per field
                    "inline": False
                })
        
        # Build embed
        embed = {
            "title": f"{self.config.direction_symbols[signal.direction.value]} {signal.symbol}/{signal.timeframe}",
            "description": f"Signal Direction: {signal.direction.value}",
            "color": color,
            "fields": fields,
        }
        
        # Add footer
        if self.config.include_footer:
            embed["footer"] = {
                "text": f"Conviction Threshold: {self.config.conviction_threshold_alert} | Analysis Only"
            }
        
        # Add timestamp
        if self.config.include_timestamp:
            embed["timestamp"] = signal.timestamp
        
        return embed
    
    def format_embeds_batch(self, signals: list[TradeSignal]) -> list:
        """Format multiple signals as Discord embeds.
        
        Args:
            signals: List of TradeSignal objects
            
        Returns:
            List of Discord embed dicts
        """
        embeds = []
        for signal in signals:
            if signal.conviction >= self.config.conviction_threshold_alert:
                embeds.append(self.format_as_embed(signal))
        
        return embeds
    
    def should_alert(self, signal: TradeSignal) -> bool:
        """Check if signal meets alert criteria.
        
        Args:
            signal: TradeSignal to evaluate
            
        Returns:
            True if signal should trigger alert
        """
        # Check conviction threshold
        if signal.conviction < self.config.conviction_threshold_alert:
            return False
        
        # Check for actionable signal
        return signal.is_actionable(min_conviction=self.config.conviction_threshold_alert)
