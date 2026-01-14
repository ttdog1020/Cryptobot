"""Alert formatting module for converting TradeSignal objects to human-readable formats.

This module provides formatters to convert trade_intelligence.TradeSignal objects
into various output formats suitable for Discord, dashboards, and other notification
systems. All formatting is analysis-only with no execution or trading logic.

Main exports:
- AlertFormatter: Base class for formatting signals
- TextAlertFormatter: Plain text format
- MarkdownAlertFormatter: Markdown format
- DiscordAlertFormatter: Discord-specific formatting with rich embeds
- RankingEngine: Sort and rank signals by conviction, momentum, regime
"""

from .signal_formatter import (
    AlertFormatter,
    TextAlertFormatter,
    MarkdownAlertFormatter,
)
from .discord_formatter import DiscordAlertFormatter
from .ranking_engine import RankingEngine, RankingConfig

__all__ = [
    "AlertFormatter",
    "TextAlertFormatter",
    "MarkdownAlertFormatter",
    "DiscordAlertFormatter",
    "RankingEngine",
    "RankingConfig",
]
