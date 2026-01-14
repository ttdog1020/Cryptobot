"""Tests for alert_formatting module."""

import pytest
from datetime import datetime, timezone

from trade_intelligence import (
    TradeSignal, SignalDirection, SignalConfidence, RegimeType,
    RiskFlags
)
from alert_formatting import (
    AlertFormatter, TextAlertFormatter, MarkdownAlertFormatter,
    DiscordAlertFormatter, RankingEngine, RankingConfig
)
from alert_formatting.signal_formatter import FormatterConfig
from alert_formatting.discord_formatter import DiscordConfig
from alert_formatting.ranking_engine import SortCriteria


# ========== Fixtures ==========

@pytest.fixture
def sample_signal_long():
    """Create sample LONG signal."""
    return TradeSignal(
        direction=SignalDirection.LONG,
        conviction=0.85,
        symbol="BTCUSDT",
        timeframe="1h",
        regime=RegimeType.TRENDING,
        timestamp="2025-01-14T12:00:00Z",
        num_strategies=3,
        agreeing_strategies=3,
        agreement_ratio=1.0,
        risk_flags=RiskFlags(
            volatility_spike=False,
            low_liquidity=False,
            drawdown_risk=False,
            conflicting_signals=False
        ),
        strategy_names=["EMA_RSI", "MACD", "Bollinger"],
        volatility_percentile=45.0,
        metadata={
            "rationale": "EMA crossover confirmed by RSI + MACD confluence",
            "entry_price": 42500.0,
            "sl_distance": 10.0,
            "tp_distance": 30.0
        }
    )


@pytest.fixture
def sample_signal_short():
    """Create sample SHORT signal."""
    return TradeSignal(
        direction=SignalDirection.SHORT,
        conviction=0.65,
        symbol="ETHUSDT",
        timeframe="4h",
        regime=RegimeType.RANGING,
        timestamp="2025-01-14T12:00:00Z",
        num_strategies=2,
        agreeing_strategies=1,
        agreement_ratio=0.5,
        risk_flags=RiskFlags(
            volatility_spike=True,
            low_liquidity=False,
            drawdown_risk=False,
            conflicting_signals=True
        ),
        strategy_names=["RSI_Divergence", "Stoch"],
        volatility_percentile=75.0,
        metadata={"rationale": "RSI divergence at resistance"}
    )


@pytest.fixture
def sample_signal_flat():
    """Create sample FLAT signal (no trade)."""
    return TradeSignal(
        direction=SignalDirection.FLAT,
        conviction=0.25,
        symbol="ADAUSDT",
        timeframe="15m",
        regime=RegimeType.NEUTRAL,
        timestamp="2025-01-14T12:00:00Z",
        num_strategies=4,
        agreeing_strategies=1,
        agreement_ratio=0.25,
        risk_flags=RiskFlags(
            volatility_spike=False,
            low_liquidity=True,
            drawdown_risk=True,
            conflicting_signals=False
        ),
        strategy_names=["MA", "RSI", "MACD", "ATR"],
        volatility_percentile=15.0,
        metadata={"rationale": "Conflicting signals, low conviction"}
    )


@pytest.fixture
def formatter_config():
    """Create formatter configuration."""
    return FormatterConfig(
        decimal_places=3,
        include_metadata=True,
        include_risk_flags=True,
        include_strategy_names=True,
        include_timestamp=True
    )


# ========== TestTradeSignalFormatting ==========

class TestTradeSignalFormatting:
    """Test basic signal formatting."""
    
    def test_text_formatter_long_signal(self, sample_signal_long, formatter_config):
        """Test formatting LONG signal as plain text."""
        formatter = TextAlertFormatter(formatter_config)
        result = formatter.format_signal(sample_signal_long)
        
        assert "BUY" in result or "LONG" in result
        assert "BTCUSDT" in result
        assert "1h" in result
        assert "0.85" in result or "85" in result  # Conviction
        assert "TRENDING" in result
        
    def test_text_formatter_short_signal(self, sample_signal_short, formatter_config):
        """Test formatting SHORT signal as plain text."""
        formatter = TextAlertFormatter(formatter_config)
        result = formatter.format_signal(sample_signal_short)
        
        assert "SELL" in result or "SHORT" in result
        assert "ETHUSDT" in result
        assert "4h" in result
        assert "0.65" in result or "65" in result
        
    def test_text_formatter_flat_signal(self, sample_signal_flat, formatter_config):
        """Test formatting FLAT signal as plain text."""
        formatter = TextAlertFormatter(formatter_config)
        result = formatter.format_signal(sample_signal_flat)
        
        assert "HOLD" in result or "FLAT" in result
        assert "ADAUSDT" in result
        
    def test_text_formatter_multiple_signals(self, sample_signal_long, sample_signal_short, formatter_config):
        """Test formatting multiple signals."""
        formatter = TextAlertFormatter(formatter_config)
        signals = [sample_signal_long, sample_signal_short]
        result = formatter.format_signals(signals)
        
        assert "BTCUSDT" in result
        assert "ETHUSDT" in result
        assert "[1/2]" in result or "1" in result
        assert "[2/2]" in result or "2" in result
        
    def test_text_formatter_empty_signals(self, formatter_config):
        """Test formatting empty signal list."""
        formatter = TextAlertFormatter(formatter_config)
        result = formatter.format_signals([])
        
        assert "No signals" in result or "empty" in result.lower()


# ========== TestMarkdownFormatting ==========

class TestMarkdownFormatting:
    """Test markdown formatting."""
    
    def test_markdown_formatter_long_signal(self, sample_signal_long, formatter_config):
        """Test formatting LONG signal as markdown."""
        formatter = MarkdownAlertFormatter(formatter_config)
        result = formatter.format_signal(sample_signal_long)
        
        assert "##" in result  # Markdown header
        assert "BTCUSDT" in result
        assert "**" in result  # Markdown bold
        assert "TRENDING" in result
        
    def test_markdown_formatter_includes_rationale(self, sample_signal_long, formatter_config):
        """Test markdown includes rationale in blockquote."""
        formatter = MarkdownAlertFormatter(formatter_config)
        result = formatter.format_signal(sample_signal_long)
        
        assert ">" in result  # Blockquote
        assert "EMA crossover" in result
        
    def test_markdown_formatter_multiple_signals(self, sample_signal_long, sample_signal_short, formatter_config):
        """Test formatting multiple signals in markdown."""
        formatter = MarkdownAlertFormatter(formatter_config)
        signals = [sample_signal_long, sample_signal_short]
        result = formatter.format_signals(signals)
        
        assert "Trade Signals Report" in result
        assert "---" in result  # Separator
        assert "BTCUSDT" in result
        assert "ETHUSDT" in result


# ========== TestDiscordFormatting ==========

class TestDiscordFormatting:
    """Test Discord formatting."""
    
    def test_discord_formatter_text_message(self, sample_signal_long):
        """Test Discord text message formatting."""
        config = DiscordConfig()
        formatter = DiscordAlertFormatter(config)
        result = formatter.format_signal(sample_signal_long)
        
        assert "LONG" in result
        assert "BTCUSDT" in result
        assert "1h" in result
        
    def test_discord_formatter_embed_dict(self, sample_signal_long):
        """Test Discord embed generation."""
        config = DiscordConfig()
        formatter = DiscordAlertFormatter(config)
        embed = formatter.format_as_embed(sample_signal_long)
        
        assert isinstance(embed, dict)
        assert "title" in embed
        assert "color" in embed
        assert "fields" in embed
        assert embed["color"] == 0x00FF00  # Green for LONG
        
    def test_discord_embed_has_fields(self, sample_signal_long):
        """Test Discord embed has required fields."""
        config = DiscordConfig()
        formatter = DiscordAlertFormatter(config)
        embed = formatter.format_as_embed(sample_signal_long)
        
        field_names = [f["name"] for f in embed["fields"]]
        assert "Conviction" in field_names
        assert "Regime" in field_names
        assert "Agreement" in field_names
        
    def test_discord_short_embed_color(self, sample_signal_short):
        """Test Discord embed color for SHORT signal."""
        config = DiscordConfig()
        formatter = DiscordAlertFormatter(config)
        embed = formatter.format_as_embed(sample_signal_short)
        
        assert embed["color"] == 0xFF0000  # Red for SHORT
        
    def test_discord_conviction_threshold(self, sample_signal_flat):
        """Test Discord conviction threshold filtering."""
        config = DiscordConfig(conviction_threshold_alert=0.6)
        formatter = DiscordAlertFormatter(config)
        
        # FLAT signal has conviction 0.25, below threshold
        result = formatter.format_signal(sample_signal_flat)
        assert "below alert threshold" in result
        
    def test_discord_embeds_batch(self, sample_signal_long, sample_signal_short, sample_signal_flat):
        """Test batch embed generation."""
        config = DiscordConfig(conviction_threshold_alert=0.6)
        formatter = DiscordAlertFormatter(config)
        signals = [sample_signal_long, sample_signal_short, sample_signal_flat]
        
        embeds = formatter.format_embeds_batch(signals)
        
        # Only long and short should be included (flat below threshold)
        assert len(embeds) == 2
        
    def test_discord_should_alert(self, sample_signal_long, sample_signal_flat):
        """Test alert trigger logic."""
        config = DiscordConfig(conviction_threshold_alert=0.6)
        formatter = DiscordAlertFormatter(config)
        
        assert formatter.should_alert(sample_signal_long) is True
        assert formatter.should_alert(sample_signal_flat) is False


# ========== TestRankingEngine ==========

class TestRankingEngine:
    """Test signal ranking and sorting."""
    
    def test_rank_by_conviction_desc(self, sample_signal_long, sample_signal_short, sample_signal_flat):
        """Test ranking by conviction descending."""
        config = RankingConfig(primary_sort=SortCriteria.CONVICTION_DESC)
        engine = RankingEngine(config)
        signals = [sample_signal_flat, sample_signal_long, sample_signal_short]
        
        ranked = engine.rank_signals(signals)
        
        assert ranked[0] == sample_signal_long  # 0.85
        assert ranked[1] == sample_signal_short  # 0.65
        assert ranked[2] == sample_signal_flat   # 0.25
        
    def test_rank_by_agreement(self, sample_signal_long, sample_signal_short):
        """Test ranking by agreement ratio."""
        config = RankingConfig(primary_sort=SortCriteria.AGREEMENT_DESC)
        engine = RankingEngine(config)
        signals = [sample_signal_short, sample_signal_long]
        
        ranked = engine.rank_signals(signals)
        
        assert ranked[0] == sample_signal_long  # 1.0 agreement
        assert ranked[1] == sample_signal_short  # 0.5 agreement
        
    def test_get_top_signals(self, sample_signal_long, sample_signal_short, sample_signal_flat):
        """Test getting top N signals."""
        config = RankingConfig(primary_sort=SortCriteria.CONVICTION_DESC)
        engine = RankingEngine(config)
        signals = [sample_signal_flat, sample_signal_long, sample_signal_short]
        
        top_2 = engine.get_top_signals(signals, n=2)
        
        assert len(top_2) == 2
        assert top_2[0] == sample_signal_long
        assert top_2[1] == sample_signal_short
        
    def test_group_by_direction(self, sample_signal_long, sample_signal_short, sample_signal_flat):
        """Test grouping signals by direction."""
        engine = RankingEngine()
        signals = [sample_signal_long, sample_signal_short, sample_signal_flat]
        
        groups = engine.group_by_direction(signals)
        
        assert len(groups[SignalDirection.LONG]) == 1
        assert len(groups[SignalDirection.SHORT]) == 1
        assert len(groups[SignalDirection.FLAT]) == 1
        
    def test_group_by_symbol(self, sample_signal_long, sample_signal_short):
        """Test grouping signals by symbol."""
        engine = RankingEngine()
        signals = [sample_signal_long, sample_signal_short]
        
        groups = engine.group_by_symbol(signals)
        
        assert "BTCUSDT" in groups
        assert "ETHUSDT" in groups
        assert len(groups["BTCUSDT"]) == 1
        assert len(groups["ETHUSDT"]) == 1
        
    def test_signal_summary(self, sample_signal_long, sample_signal_short, sample_signal_flat):
        """Test signal summary statistics."""
        engine = RankingEngine()
        signals = [sample_signal_long, sample_signal_short, sample_signal_flat]
        
        summary = engine.get_signal_summary(signals)
        
        assert summary["total"] == 3
        assert summary["long_count"] == 1
        assert summary["short_count"] == 1
        assert summary["flat_count"] == 1
        assert summary["high_conviction_count"] == 1  # Only long >= 0.7
        assert summary["high_risk_count"] == 2  # short and flat have risk flags
        
    def test_min_conviction_filter(self, sample_signal_long, sample_signal_short, sample_signal_flat):
        """Test filtering by minimum conviction."""
        config = RankingConfig(min_conviction=0.6)
        engine = RankingEngine(config)
        signals = [sample_signal_long, sample_signal_short, sample_signal_flat]
        
        filtered = engine.rank_signals(signals)
        
        assert len(filtered) == 2
        assert sample_signal_flat not in filtered
        
    def test_direction_filter(self, sample_signal_long, sample_signal_short, sample_signal_flat):
        """Test filtering by direction."""
        config = RankingConfig(direction_filter=SignalDirection.LONG)
        engine = RankingEngine(config)
        signals = [sample_signal_long, sample_signal_short, sample_signal_flat]
        
        filtered = engine.rank_signals(signals)
        
        assert len(filtered) == 1
        assert filtered[0] == sample_signal_long
        
    def test_exclude_high_risk(self, sample_signal_long, sample_signal_short):
        """Test excluding high-risk signals."""
        config = RankingConfig(exclude_high_risk=True)
        engine = RankingEngine(config)
        signals = [sample_signal_long, sample_signal_short]
        
        filtered = engine.rank_signals(signals)
        
        assert len(filtered) == 1
        assert filtered[0] == sample_signal_long
        
    def test_combined_scoring(self, sample_signal_long, sample_signal_short):
        """Test combined scoring metric."""
        config = RankingConfig(
            primary_sort=SortCriteria.COMBINED,
            conviction_weight=0.5,
            agreement_weight=0.3,
            regime_weight=0.2
        )
        engine = RankingEngine(config)
        signals = [sample_signal_short, sample_signal_long]
        
        ranked = engine.rank_signals(signals)
        
        # Long signal should rank higher (better conviction, agreement, regime)
        assert ranked[0] == sample_signal_long
        
    def test_empty_signals_summary(self):
        """Test summary with empty signals."""
        engine = RankingEngine()
        summary = engine.get_signal_summary([])
        
        assert summary["total"] == 0
        assert summary["long_count"] == 0
        assert summary["avg_conviction"] == 0.0


# ========== TestEdgeCases ==========

class TestEdgeCases:
    """Test edge cases and corner cases."""
    
    def test_formatter_with_none_config(self, sample_signal_long):
        """Test formatters with default None config."""
        formatter = TextAlertFormatter()  # None config
        result = formatter.format_signal(sample_signal_long)
        
        assert result is not None
        assert len(result) > 0
        
    def test_signal_with_empty_strategy_names(self):
        """Test formatting signal with no strategy names."""
        signal = TradeSignal(
            direction=SignalDirection.LONG,
            conviction=0.7,
            symbol="TEST",
            timeframe="1h",
            regime=RegimeType.TRENDING,
            num_strategies=1,
            agreeing_strategies=1,
            agreement_ratio=1.0,
            risk_flags=RiskFlags(False, False, False, False),
            strategy_names=[],
            volatility_percentile=50.0,
            metadata={}
        )
        
        formatter = TextAlertFormatter()
        result = formatter.format_signal(signal)
        
        assert result is not None
        
    def test_signal_with_special_characters(self):
        """Test formatting signal with special characters in metadata."""
        signal = TradeSignal(
            direction=SignalDirection.LONG,
            conviction=0.8,
            symbol="BTC/USD",
            timeframe="1h",
            regime=RegimeType.TRENDING,
            num_strategies=2,
            agreeing_strategies=2,
            agreement_ratio=1.0,
            risk_flags=RiskFlags(False, False, False, False),
            strategy_names=["Test_Strategy-1"],
            volatility_percentile=50.0,
            metadata={"rationale": "Test with $pecial ch@rs!"}
        )
        
        formatter = MarkdownAlertFormatter()
        result = formatter.format_signal(signal)
        
        assert result is not None
        assert len(result) > 0
        assert "BTC/USD" in result or "btc" in result.lower()
        assert "$" in result  # Metadata with $ symbol should be preserved
        
    def test_ranking_with_duplicate_conviction(self):
        """Test ranking when signals have same conviction."""
        signal1 = TradeSignal(
            direction=SignalDirection.LONG,
            conviction=0.7,
            symbol="BTC",
            timeframe="1h",
            regime=RegimeType.TRENDING,
            num_strategies=1,
            agreeing_strategies=1,
            agreement_ratio=1.0,
            risk_flags=RiskFlags(False, False, False, False),
            strategy_names=["S1"],
            volatility_percentile=50.0
        )
        
        signal2 = TradeSignal(
            direction=SignalDirection.SHORT,
            conviction=0.7,
            symbol="ETH",
            timeframe="1h",
            regime=RegimeType.RANGING,
            num_strategies=1,
            agreeing_strategies=1,
            agreement_ratio=1.0,
            risk_flags=RiskFlags(False, False, False, False),
            strategy_names=["S2"],
            volatility_percentile=50.0
        )
        
        config = RankingConfig(primary_sort=SortCriteria.CONVICTION_DESC)
        engine = RankingEngine(config)
        ranked = engine.rank_signals([signal2, signal1])
        
        # Both should be in result
        assert len(ranked) == 2
        assert signal1 in ranked
        assert signal2 in ranked


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
