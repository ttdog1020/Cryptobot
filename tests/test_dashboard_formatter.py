"""Tests for dashboard formatter."""

import pytest
from trade_intelligence import (
    TradeSignal,
    SignalDirection,
    RegimeType,
    DashboardFormatter,
    filter_actionable,
)


class TestDashboardFormatter:
    """Test dashboard formatting utilities."""
    
    def test_format_table_row(self):
        """Test single signal table row formatting."""
        signal = TradeSignal(
            direction=SignalDirection.LONG,
            conviction=0.75,
            symbol='BTCUSDT',
            timeframe='1h',
            regime=RegimeType.TRENDING,
            num_strategies=3,
            agreeing_strategies=2,
            agreement_ratio=0.666,
            timeframe_alignment_score=0.75,
        )
        signal.age_seconds = 120.0
        
        row = DashboardFormatter.format_table_row(signal)
        
        assert row['Symbol'] == 'BTCUSDT'
        assert row['Direction'] == 'LONG'
        assert '75' in row['Conviction']  # 75%
        assert row['Bucket'] == 'HIGH'
        assert '67%' in row['Agreement'] or '66%' in row['Agreement']
        assert row['Strategies'] == '2/3'
        assert row['Age'] == '120s'
        assert '75%' in row['TF Align']
    
    def test_format_table_multiple(self):
        """Test multiple signals table formatting."""
        signals = [
            TradeSignal(
                direction=SignalDirection.LONG,
                conviction=0.8,
                symbol='BTCUSDT',
                timeframe='1h',
            ),
            TradeSignal(
                direction=SignalDirection.SHORT,
                conviction=0.6,
                symbol='ETHUSDT',
                timeframe='4h',
            ),
        ]
        
        rows = DashboardFormatter.format_table(signals)
        
        assert len(rows) == 2
        assert rows[0]['Symbol'] == 'BTCUSDT'
        assert rows[1]['Symbol'] == 'ETHUSDT'
    
    def test_format_terminal(self):
        """Test terminal formatting with ANSI colors."""
        signal = TradeSignal(
            direction=SignalDirection.SHORT,
            conviction=0.45,
            symbol='ETHUSDT',
            timeframe='15m',
            regime=RegimeType.RANGING,
        )
        signal.explanation = "Test explanation"
        
        output = DashboardFormatter.format_terminal(signal)
        
        assert 'ETHUSDT' in output
        assert 'SHORT' in output
        assert '45' in output or '0.45' in output
        assert 'RANGING' in output
        assert 'Test explanation' in output
        assert '\033[' in output  # Has ANSI codes
    
    def test_format_terminal_without_explanation(self):
        """Test terminal formatting without explanation."""
        signal = TradeSignal(
            direction=SignalDirection.LONG,
            conviction=0.6,
            symbol='BTCUSDT',
            timeframe='1h',
        )
        
        output = DashboardFormatter.format_terminal(signal, include_explanation=False)
        
        assert 'BTCUSDT' in output
        # Should not error even without explanation field
    
    def test_format_discord(self):
        """Test Discord embed formatting."""
        signal = TradeSignal(
            direction=SignalDirection.LONG,
            conviction=0.7,
            symbol='BTCUSDT',
            timeframe='1h',
            regime=RegimeType.BREAKOUT,
            strategy_names=['ema_rsi', 'macd'],
        )
        signal.explanation = "Strong breakout signal"
        
        embed = DashboardFormatter.format_discord(signal)
        
        assert embed['title'] == 'BTCUSDT 1h'
        assert 'Strong breakout signal' in embed['description']
        assert embed['color'] == 0x00FF00  # Green for LONG
        assert any(f['name'] == 'Direction' for f in embed['fields'])
        assert any(f['name'] == 'Conviction' for f in embed['fields'])
    
    def test_format_discord_with_risks(self):
        """Test Discord formatting includes risk flags."""
        signal = TradeSignal(
            direction=SignalDirection.SHORT,
            conviction=0.5,
            symbol='ETHUSDT',
            timeframe='4h',
        )
        signal.risk_flags.volatility_spike = True
        signal.risk_flags.low_liquidity = True
        
        embed = DashboardFormatter.format_discord(signal)
        
        # Should have risk flag field
        risk_field = next((f for f in embed['fields'] if 'Risk' in f['name']), None)
        assert risk_field is not None
        assert 'Vol Spike' in risk_field['value']
    
    def test_format_slack(self):
        """Test Slack block formatting."""
        signal = TradeSignal(
            direction=SignalDirection.FLAT,
            conviction=0.3,
            symbol='BNBUSDT',
            timeframe='1d',
        )
        signal.explanation = "No clear direction"
        
        payload = DashboardFormatter.format_slack(signal)
        
        assert 'blocks' in payload
        assert len(payload['blocks']) > 0
        assert payload['blocks'][0]['type'] == 'header'
        assert 'BNBUSDT' in payload['blocks'][0]['text']['text']
    
    def test_format_summary(self):
        """Test summary statistics generation."""
        signals = [
            TradeSignal(direction=SignalDirection.LONG, conviction=0.8, symbol='BTC', timeframe='1h'),
            TradeSignal(direction=SignalDirection.LONG, conviction=0.6, symbol='ETH', timeframe='1h'),
            TradeSignal(direction=SignalDirection.SHORT, conviction=0.5, symbol='BNB', timeframe='1h'),
            TradeSignal(direction=SignalDirection.FLAT, conviction=0.3, symbol='ADA', timeframe='1h'),
        ]
        
        summary = DashboardFormatter.format_summary(signals)
        
        assert summary['total_signals'] == 4
        assert summary['by_direction']['LONG'] == 2
        assert summary['by_direction']['SHORT'] == 1
        assert summary['by_direction']['FLAT'] == 1
        assert 0.5 <= summary['avg_conviction'] <= 0.6
        assert summary['high_confidence_count'] == 1  # Only 0.8 is HIGH (>= 0.7)
    
    def test_format_summary_empty(self):
        """Test summary with no signals."""
        summary = DashboardFormatter.format_summary([])
        
        assert summary['total_signals'] == 0
        assert summary['avg_conviction'] == 0.0


class TestFilterActionable:
    """Test signal filtering utilities."""
    
    def test_filter_by_conviction(self):
        """Test filtering by conviction threshold."""
        signals = [
            TradeSignal(direction=SignalDirection.LONG, conviction=0.8, symbol='BTC', timeframe='1h'),
            TradeSignal(direction=SignalDirection.SHORT, conviction=0.4, symbol='ETH', timeframe='1h'),
            TradeSignal(direction=SignalDirection.LONG, conviction=0.3, symbol='BNB', timeframe='1h'),
        ]
        
        filtered = filter_actionable(signals, min_conviction=0.5)
        
        assert len(filtered) == 1
        assert filtered[0].symbol == 'BTC'
    
    def test_filter_exclude_flat(self):
        """Test excluding FLAT signals."""
        signals = [
            TradeSignal(direction=SignalDirection.LONG, conviction=0.8, symbol='BTC', timeframe='1h'),
            TradeSignal(direction=SignalDirection.FLAT, conviction=0.9, symbol='ETH', timeframe='1h'),
        ]
        
        filtered = filter_actionable(signals, min_conviction=0.5, exclude_flat=True)
        
        assert len(filtered) == 1
        assert filtered[0].direction == SignalDirection.LONG
    
    def test_filter_include_flat(self):
        """Test including FLAT signals when requested."""
        signals = [
            TradeSignal(direction=SignalDirection.LONG, conviction=0.8, symbol='BTC', timeframe='1h'),
            TradeSignal(direction=SignalDirection.FLAT, conviction=0.9, symbol='ETH', timeframe='1h'),
        ]
        
        filtered = filter_actionable(signals, min_conviction=0.5, exclude_flat=False)
        
        assert len(filtered) == 2
    
    def test_filter_by_risk_flags(self):
        """Test filtering by risk flag count."""
        signal1 = TradeSignal(direction=SignalDirection.LONG, conviction=0.8, symbol='BTC', timeframe='1h')
        signal1.risk_flags.volatility_spike = True
        signal1.risk_flags.low_liquidity = True
        signal1.risk_flags.drawdown_risk = True  # 3 flags
        
        signal2 = TradeSignal(direction=SignalDirection.SHORT, conviction=0.7, symbol='ETH', timeframe='1h')
        signal2.risk_flags.volatility_spike = True  # 1 flag
        
        signals = [signal1, signal2]
        
        filtered = filter_actionable(signals, min_conviction=0.5, max_risk_flags=1)
        
        assert len(filtered) == 1
        assert filtered[0].symbol == 'ETH'
    
    def test_filter_combined(self):
        """Test combined filtering criteria."""
        signal1 = TradeSignal(direction=SignalDirection.LONG, conviction=0.9, symbol='BTC', timeframe='1h')
        signal1.risk_flags.volatility_spike = True
        
        signal2 = TradeSignal(direction=SignalDirection.FLAT, conviction=0.8, symbol='ETH', timeframe='1h')
        
        signal3 = TradeSignal(direction=SignalDirection.SHORT, conviction=0.3, symbol='BNB', timeframe='1h')
        
        signal4 = TradeSignal(direction=SignalDirection.LONG, conviction=0.7, symbol='ADA', timeframe='1h')
        
        signals = [signal1, signal2, signal3, signal4]
        
        filtered = filter_actionable(
            signals,
            min_conviction=0.6,
            exclude_flat=True,
            max_risk_flags=0,
        )
        
        # Only signal4 passes all filters
        assert len(filtered) == 1
        assert filtered[0].symbol == 'ADA'
