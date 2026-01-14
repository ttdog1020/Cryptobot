"""
Dashboard Formatter for Trade Intelligence

Provides utilities to format TradeSignal objects for display in:
- Web dashboards
- Terminal displays
- Discord/Slack webhooks
- Log files

All formatters are read-only, analysis-only.
"""

from typing import List, Dict, Any, Optional
from .signal_model import TradeSignal, SignalDirection


class DashboardFormatter:
    """Format trade signals for dashboard display."""
    
    @staticmethod
    def format_table_row(signal: TradeSignal) -> Dict[str, Any]:
        """
        Format signal as a single table row.
        
        Returns dict suitable for pandas DataFrame or HTML table.
        
        Example:
            >>> row = DashboardFormatter.format_table_row(signal)
            >>> df = pd.DataFrame([row])
        """
        return {
            'Symbol': signal.symbol,
            'Timeframe': signal.timeframe,
            'Direction': signal.direction.value,
            'Conviction': f"{signal.conviction:.2%}",
            'Bucket': signal.confidence_bucket,
            'Regime': signal.regime.value,
            'Agreement': f"{signal.agreement_ratio:.0%}",
            'Strategies': f"{signal.agreeing_strategies}/{signal.num_strategies}",
            'Age': f"{signal.age_seconds:.0f}s" if signal.age_seconds else "0s",
            'TF Align': f"{signal.timeframe_alignment_score:.0%}" if signal.timeframe_alignment_score else "N/A",
            'Risk Flags': DashboardFormatter._format_risk_flags(signal),
            'Timestamp': signal.timestamp,
        }
    
    @staticmethod
    def format_table(signals: List[TradeSignal]) -> List[Dict[str, Any]]:
        """
        Format multiple signals as table rows.
        
        Returns list of dicts suitable for pandas DataFrame.
        
        Example:
            >>> rows = DashboardFormatter.format_table(signals)
            >>> df = pd.DataFrame(rows)
            >>> print(df.to_string())
        """
        return [DashboardFormatter.format_table_row(s) for s in signals]
    
    @staticmethod
    def format_terminal(signal: TradeSignal, include_explanation: bool = True) -> str:
        """
        Format signal for terminal/console display with ANSI colors.
        
        Args:
            signal: TradeSignal to format
            include_explanation: Whether to include explanation text
        
        Returns:
            Formatted string with color codes
        """
        # Color codes
        RESET = "\033[0m"
        BOLD = "\033[1m"
        GREEN = "\033[92m"
        RED = "\033[91m"
        YELLOW = "\033[93m"
        CYAN = "\033[96m"
        GRAY = "\033[90m"
        
        # Direction color
        if signal.direction == SignalDirection.LONG:
            dir_color = GREEN
        elif signal.direction == SignalDirection.SHORT:
            dir_color = RED
        else:
            dir_color = GRAY
        
        # Conviction color
        if signal.conviction >= 0.7:
            conv_color = GREEN
        elif signal.conviction >= 0.4:
            conv_color = YELLOW
        else:
            conv_color = RED
        
        lines = []
        
        # Header
        lines.append(f"{BOLD}{CYAN}{'=' * 70}{RESET}")
        lines.append(
            f"{BOLD}{signal.symbol}{RESET} {GRAY}[{signal.timeframe}]{RESET} "
            f"{dir_color}{signal.direction.value}{RESET}"
        )
        
        # Core metrics
        lines.append(
            f"  Conviction: {conv_color}{signal.conviction:.2%}{RESET} "
            f"({signal.confidence_bucket}) "
            f"| Agreement: {signal.agreement_ratio:.0%} "
            f"({signal.agreeing_strategies}/{signal.num_strategies})"
        )
        
        # Context
        context_parts = [f"Regime: {signal.regime.value}"]
        if signal.timeframe_alignment_score is not None:
            context_parts.append(f"TF Align: {signal.timeframe_alignment_score:.0%}")
        if signal.age_seconds:
            context_parts.append(f"Age: {signal.age_seconds:.0f}s")
        lines.append(f"  {' | '.join(context_parts)}")
        
        # Risk flags
        risk_flags = DashboardFormatter._format_risk_flags(signal)
        if risk_flags != "None":
            lines.append(f"  {YELLOW}⚠ Risks: {risk_flags}{RESET}")
        
        # Explanation
        if include_explanation and signal.explanation:
            lines.append(f"  {GRAY}{signal.explanation}{RESET}")
        
        lines.append(f"{CYAN}{'=' * 70}{RESET}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_discord(signal: TradeSignal) -> Dict[str, Any]:
        """
        Format signal as Discord embed payload.
        
        Returns dict ready for Discord webhook POST.
        
        Example:
            >>> embed = DashboardFormatter.format_discord(signal)
            >>> requests.post(webhook_url, json={'embeds': [embed]})
        """
        # Color based on direction
        if signal.direction == SignalDirection.LONG:
            color = 0x00FF00  # Green
        elif signal.direction == SignalDirection.SHORT:
            color = 0xFF0000  # Red
        else:
            color = 0x808080  # Gray
        
        # Build fields
        fields = [
            {
                'name': 'Direction',
                'value': signal.direction.value,
                'inline': True,
            },
            {
                'name': 'Conviction',
                'value': f"{signal.conviction:.1%} ({signal.confidence_bucket})",
                'inline': True,
            },
            {
                'name': 'Agreement',
                'value': f"{signal.agreement_ratio:.0%} ({signal.agreeing_strategies}/{signal.num_strategies})",
                'inline': True,
            },
            {
                'name': 'Regime',
                'value': signal.regime.value,
                'inline': True,
            },
        ]
        
        # Optional fields
        if signal.timeframe_alignment_score is not None:
            fields.append({
                'name': 'TF Alignment',
                'value': f"{signal.timeframe_alignment_score:.0%}",
                'inline': True,
            })
        
        risk_flags = DashboardFormatter._format_risk_flags(signal)
        if risk_flags != "None":
            fields.append({
                'name': '⚠️ Risk Flags',
                'value': risk_flags,
                'inline': False,
            })
        
        return {
            'title': f"{signal.symbol} {signal.timeframe}",
            'description': signal.explanation or signal.rationale or "No explanation available",
            'color': color,
            'fields': fields,
            'footer': {
                'text': f"Strategies: {', '.join(signal.strategy_names[:3])}{'...' if len(signal.strategy_names) > 3 else ''}"
            },
            'timestamp': signal.timestamp,
        }
    
    @staticmethod
    def format_slack(signal: TradeSignal) -> Dict[str, Any]:
        """
        Format signal as Slack block payload.
        
        Returns dict ready for Slack webhook POST.
        
        Example:
            >>> payload = DashboardFormatter.format_slack(signal)
            >>> requests.post(webhook_url, json=payload)
        """
        # Direction emoji
        if signal.direction == SignalDirection.LONG:
            emoji = "📈"
        elif signal.direction == SignalDirection.SHORT:
            emoji = "📉"
        else:
            emoji = "➖"
        
        blocks = [
            {
                'type': 'header',
                'text': {
                    'type': 'plain_text',
                    'text': f"{emoji} {signal.symbol} {signal.timeframe} - {signal.direction.value}",
                }
            },
            {
                'type': 'section',
                'fields': [
                    {
                        'type': 'mrkdwn',
                        'text': f"*Conviction:*\n{signal.conviction:.1%} ({signal.confidence_bucket})",
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f"*Agreement:*\n{signal.agreement_ratio:.0%} ({signal.agreeing_strategies}/{signal.num_strategies})",
                    },
                    {
                        'type': 'mrkdwn',
                        'text': f"*Regime:*\n{signal.regime.value}",
                    },
                ]
            },
        ]
        
        # Add explanation if available
        if signal.explanation:
            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f"_{signal.explanation}_",
                }
            })
        
        # Add risk warnings if present
        risk_flags = DashboardFormatter._format_risk_flags(signal)
        if risk_flags != "None":
            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f":warning: *Risks:* {risk_flags}",
                }
            })
        
        return {'blocks': blocks}
    
    @staticmethod
    def format_summary(signals: List[TradeSignal]) -> Dict[str, Any]:
        """
        Generate summary statistics for a list of signals.
        
        Useful for dashboard overview widgets.
        
        Returns:
            Dict with aggregate metrics
        """
        if not signals:
            return {
                'total_signals': 0,
                'by_direction': {},
                'avg_conviction': 0.0,
                'high_confidence_count': 0,
            }
        
        by_direction = {}
        total_conviction = 0.0
        high_conf_count = 0
        
        for signal in signals:
            # Count by direction
            dir_str = signal.direction.value
            by_direction[dir_str] = by_direction.get(dir_str, 0) + 1
            
            # Sum conviction
            total_conviction += signal.conviction
            
            # Count high confidence
            if signal.confidence_bucket == "HIGH":
                high_conf_count += 1
        
        return {
            'total_signals': len(signals),
            'by_direction': by_direction,
            'avg_conviction': total_conviction / len(signals),
            'high_confidence_count': high_conf_count,
            'high_confidence_pct': high_conf_count / len(signals),
        }
    
    @staticmethod
    def _format_risk_flags(signal: TradeSignal) -> str:
        """Format risk flags as comma-separated string."""
        flags = []
        if signal.risk_flags.volatility_spike:
            flags.append("Vol Spike")
        if signal.risk_flags.low_liquidity:
            flags.append("Low Liq")
        if signal.risk_flags.drawdown_risk:
            flags.append("Drawdown")
        if signal.risk_flags.conflicting_signals:
            flags.append("Conflict")
        
        return ", ".join(flags) if flags else "None"


def filter_actionable(
    signals: List[TradeSignal],
    min_conviction: float = 0.5,
    exclude_flat: bool = True,
    max_risk_flags: Optional[int] = None,
) -> List[TradeSignal]:
    """
    Filter signals to actionable subset.
    
    Args:
        signals: List of TradeSignal objects
        min_conviction: Minimum conviction threshold
        exclude_flat: Whether to exclude FLAT signals
        max_risk_flags: Maximum number of risk flags allowed (None = no limit)
    
    Returns:
        Filtered list of signals
    """
    filtered = []
    
    for signal in signals:
        # Check conviction
        if signal.conviction < min_conviction:
            continue
        
        # Check direction
        if exclude_flat and signal.direction == SignalDirection.FLAT:
            continue
        
        # Check risk flags
        if max_risk_flags is not None:
            risk_count = sum([
                signal.risk_flags.volatility_spike,
                signal.risk_flags.low_liquidity,
                signal.risk_flags.drawdown_risk,
                signal.risk_flags.conflicting_signals,
            ])
            if risk_count > max_risk_flags:
                continue
        
        filtered.append(signal)
    
    return filtered
