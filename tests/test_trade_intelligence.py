"""
Tests for Trade Intelligence Module

Coverage:
- Signal model serialization
- Confidence scoring
- Risk context detection
- Multi-strategy aggregation
- Signal engine orchestration
- Edge cases
"""

import pytest
from pathlib import Path
import json
import tempfile

from trade_intelligence import (
    TradeSignal,
    SignalDirection,
    SignalConfidence,
    SignalEngine,
    ConfidenceCalculator,
    RiskContextAnalyzer,
)
from trade_intelligence.signal_model import RegimeType, RiskFlags
from trade_intelligence.aggregation import SignalAggregator, StrategyOutputFormat, StrategyAdapter


# ============================================================================
# Signal Model Tests
# ============================================================================

class TestTradeSignal:
    """Test TradeSignal data model."""
    
    def test_signal_creation(self):
        """Test basic signal creation."""
        signal = TradeSignal(
            direction=SignalDirection.LONG,
            conviction=0.75,
            symbol='BTCUSDT',
            timeframe='1h',
        )
        
        assert signal.direction == SignalDirection.LONG
        assert signal.conviction == 0.75
        assert signal.symbol == 'BTCUSDT'
        assert signal.timeframe == '1h'
    
    def test_confidence_categorization(self):
        """Test automatic confidence category assignment."""
        test_cases = [
            (0.95, SignalConfidence.VERY_HIGH),
            (0.70, SignalConfidence.HIGH),
            (0.50, SignalConfidence.MEDIUM),
            (0.30, SignalConfidence.LOW),
            (0.10, SignalConfidence.VERY_LOW),
        ]
        
        for conviction, expected_cat in test_cases:
            signal = TradeSignal(
                direction=SignalDirection.LONG,
                conviction=conviction,
                symbol='BTCUSDT',
                timeframe='1h',
            )
            assert signal.confidence_category == expected_cat
    
    def test_signal_serialization(self):
        """Test JSON serialization."""
        signal = TradeSignal(
            direction=SignalDirection.LONG,
            conviction=0.75,
            symbol='BTCUSDT',
            timeframe='1h',
            regime=RegimeType.TRENDING,
            strategy_names=['ema_rsi', 'macd'],
            tags=['confluence', 'breakout'],
        )
        
        signal_dict = signal.to_dict()
        
        assert signal_dict['direction'] == 'LONG'
        assert signal_dict['conviction'] == 0.75
        assert signal_dict['symbol'] == 'BTCUSDT'
        assert signal_dict['confidence_category'] == 'HIGH'
        
        # Ensure JSON serializable
        json_str = json.dumps(signal_dict)
        reloaded = json.loads(json_str)
        assert reloaded['direction'] == 'LONG'
    
    def test_is_actionable(self):
        """Test actionable signal filter."""
        high_conf = TradeSignal(
            direction=SignalDirection.LONG,
            conviction=0.75,
            symbol='BTCUSDT',
            timeframe='1h',
        )
        assert high_conf.is_actionable(min_conviction=0.5)
        
        low_conf = TradeSignal(
            direction=SignalDirection.LONG,
            conviction=0.3,
            symbol='BTCUSDT',
            timeframe='1h',
        )
        assert not low_conf.is_actionable(min_conviction=0.5)
        
        flat = TradeSignal(
            direction=SignalDirection.FLAT,
            conviction=0.75,
            symbol='BTCUSDT',
            timeframe='1h',
        )
        assert not flat.is_actionable(min_conviction=0.5)


# ============================================================================
# Confidence Calculator Tests
# ============================================================================

class TestConfidenceCalculator:
    """Test conviction scoring."""
    
    def test_agreement_score_single_strategy(self):
        """Test agreement score with 1 strategy."""
        calc = ConfidenceCalculator()
        score = calc.compute_agreement_score(num_strategies=1, agreeing_count=1)
        
        # Single strategy: no decay (1 strategy = 0 decay penalty)
        assert score == 1.0
    
    def test_agreement_score_full_consensus(self):
        """Test agreement score with full consensus."""
        calc = ConfidenceCalculator()
        score = calc.compute_agreement_score(num_strategies=3, agreeing_count=3)
        
        # Full agreement should score high
        assert score > 0.8
    
    def test_agreement_score_partial(self):
        """Test agreement score with partial consensus."""
        calc = ConfidenceCalculator()
        score = calc.compute_agreement_score(num_strategies=3, agreeing_count=2)
        
        # 2/3 agreement should be decent
        assert 0.5 < score < 0.8
    
    def test_volatility_normalization(self):
        """Test volatility normalization component."""
        calc = ConfidenceCalculator()
        
        # Low vol (good for trading)
        low = calc.compute_volatility_normalization(10)
        assert 0.6 < low < 0.8
        
        # Mid vol (optimal)
        mid = calc.compute_volatility_normalization(50)
        assert mid > 0.85
        
        # High vol (risky)
        high = calc.compute_volatility_normalization(90)
        assert high < 0.5
    
    def test_historical_score(self):
        """Test historical win rate component."""
        calc = ConfidenceCalculator()
        
        score = calc.compute_historical_score(win_rate=0.65)
        assert score == 0.65
        
        # Clamps to [0.2, 1.0]
        low = calc.compute_historical_score(win_rate=0.05)
        assert low == 0.2
    
    def test_conviction_combination(self):
        """Test full conviction score calculation."""
        calc = ConfidenceCalculator()
        
        conviction = calc.compute_conviction(
            num_strategies=3,
            agreeing_count=3,
            volatility_percentile=50,
            win_rate=0.60,
        )
        
        # Should be high when everything aligns
        assert 0.6 < conviction < 1.0


# ============================================================================
# Risk Context Tests
# ============================================================================

class TestRiskContextAnalyzer:
    """Test risk detection."""
    
    def test_volatility_spike_detection(self):
        """Test volatility spike detection."""
        analyzer = RiskContextAnalyzer(vol_spike_threshold=1.5)
        
        # No spike
        assert not analyzer.detect_volatility_spike(1.0, 1.0)
        
        # Spike detected
        assert analyzer.detect_volatility_spike(2.0, 1.0)
    
    def test_low_liquidity_detection(self):
        """Test low liquidity detection."""
        analyzer = RiskContextAnalyzer()
        
        # Normal liquidity
        assert not analyzer.detect_low_liquidity(1000, 1000)
        
        # Low liquidity (50% of average)
        assert analyzer.detect_low_liquidity(400, 1000)
    
    def test_drawdown_risk_detection(self):
        """Test drawdown risk detection."""
        analyzer = RiskContextAnalyzer(drawdown_threshold=0.10)
        
        # No drawdown
        assert not analyzer.detect_drawdown_risk(1000, 1000)
        
        # 5% drawdown (below threshold)
        assert not analyzer.detect_drawdown_risk(950, 1000)
        
        # 15% drawdown (above threshold)
        assert analyzer.detect_drawdown_risk(850, 1000)
    
    def test_conflicting_signals_detection(self):
        """Test conflicting signals detection."""
        analyzer = RiskContextAnalyzer()
        
        # Unanimous
        assert not analyzer.detect_conflicting_signals(3, 3)
        
        # 2/3 agreement (33% dissent)
        assert analyzer.detect_conflicting_signals(3, 2)
        
        # 3/4 agreement (25% dissent)
        assert not analyzer.detect_conflicting_signals(4, 3)


# ============================================================================
# Aggregation Tests
# ============================================================================

class TestStrategyAdapter:
    """Test strategy output adapters."""
    
    def test_trade_intent_format(self):
        """Test TradeIntent format adapter."""
        adapter = StrategyAdapter(StrategyOutputFormat.TRADE_INTENT)
        
        output = {'signal': 'LONG', 'confidence': 0.8, 'metadata': {'reason': 'test'}}
        normalized = adapter.normalize(output)
        
        assert normalized['signal'] == 'LONG'
        assert normalized['confidence'] == 0.8
    
    def test_signal_dict_format(self):
        """Test SignalDict format adapter."""
        adapter = StrategyAdapter(StrategyOutputFormat.SIGNAL_DICT)
        
        output = {'signal': 'SHORT'}
        normalized = adapter.normalize(output)
        
        assert normalized['signal'] == 'SHORT'
        assert normalized['confidence'] == 0.5  # Default
    
    def test_boolean_format(self):
        """Test Boolean format adapter."""
        adapter = StrategyAdapter(StrategyOutputFormat.BOOLEAN)
        
        # True = LONG
        normalized_true = adapter.normalize(True)
        assert normalized_true['signal'] == 'LONG'
        
        # False = FLAT
        normalized_false = adapter.normalize(False)
        assert normalized_false['signal'] == 'FLAT'


class TestSignalAggregator:
    """Test multi-strategy aggregation."""
    
    def test_single_strategy_consensus(self):
        """Test single strategy case."""
        agg = SignalAggregator()
        
        result = agg.aggregate({
            'ema_rsi': {'signal': 'LONG'},
        })
        
        assert result['direction'] == 'LONG'
        assert result['agreeing'] == 1
        assert result['agreement_ratio'] == 1.0
    
    def test_conflicting_strategies(self):
        """Test conflicting strategy outputs."""
        agg = SignalAggregator()
        
        result = agg.aggregate({
            'ema_rsi': {'signal': 'LONG'},
            'macd': {'signal': 'SHORT'},
            'bb_squeeze': {'signal': 'FLAT'},
        })
        
        # LONG and SHORT split, FLAT breaks tie -> FLAT
        assert result['direction'] == 'FLAT'
        assert result['num_strategies'] == 3
    
    def test_consensus_2_3(self):
        """Test 2/3 agreement."""
        agg = SignalAggregator()
        
        result = agg.aggregate({
            'ema_rsi': {'signal': 'LONG'},
            'macd': {'signal': 'LONG'},
            'bb_squeeze': {'signal': 'FLAT'},
        })
        
        assert result['direction'] == 'LONG'
        assert result['agreeing'] == 2
        assert result['agreement_ratio'] == pytest.approx(0.667, rel=0.01)
    
    def test_no_trade_signal(self):
        """Test all strategies say FLAT."""
        agg = SignalAggregator()
        
        result = agg.aggregate({
            'ema_rsi': {'signal': 'FLAT'},
            'macd': {'signal': 'FLAT'},
        })
        
        assert result['direction'] == 'FLAT'


# ============================================================================
# Signal Engine Tests
# ============================================================================

class TestSignalEngine:
    """Test main signal engine orchestration."""
    
    def test_engine_initialization(self):
        """Test engine creation."""
        engine = SignalEngine()
        
        assert engine.aggregator is not None
        assert engine.confidence_calc is not None
        assert engine.risk_analyzer is not None
    
    def test_single_strategy_generation(self):
        """Test signal generation from single strategy."""
        engine = SignalEngine()
        engine.register_strategy('ema_rsi')
        
        signal = engine.generate_signal(
            strategy_outputs={'ema_rsi': {'signal': 'LONG'}},
            symbol='BTCUSDT',
            timeframe='1h',
        )
        
        assert signal.direction == SignalDirection.LONG
        assert signal.symbol == 'BTCUSDT'
        assert signal.timeframe == '1h'
        assert signal.num_strategies == 1
    
    def test_multi_strategy_generation(self):
        """Test signal generation from multiple strategies."""
        engine = SignalEngine()
        engine.register_strategy('ema_rsi')
        engine.register_strategy('macd')
        
        signal = engine.generate_signal(
            strategy_outputs={
                'ema_rsi': {'signal': 'LONG'},
                'macd': {'signal': 'LONG'},
            },
            symbol='ETHUSDT',
            timeframe='4h',
            regime='TRENDING',
            volatility_percentile=50,
        )
        
        assert signal.direction == SignalDirection.LONG
        assert signal.num_strategies == 2
        assert signal.agreeing_strategies == 2
        assert signal.agreement_ratio == 1.0
        assert signal.regime == RegimeType.TRENDING
    
    def test_risk_context_integration(self):
        """Test risk context in signal generation."""
        engine = SignalEngine(vol_spike_threshold=1.4)
        
        signal = engine.generate_signal(
            strategy_outputs={'ema_rsi': {'signal': 'LONG'}},
            symbol='BTCUSDT',
            timeframe='1h',
            current_volatility=2.0,
            volatility_sma=1.0,  # Spike! (2.0 / 1.0 = 2.0 > 1.4)
            volume=400,
            volume_sma=1000,     # Low liquidity! (400 / 1000 = 0.4 < 0.5)
        )
        
        assert signal.risk_flags.volatility_spike
        assert signal.risk_flags.low_liquidity
    
    def test_batch_generation(self):
        """Test batch signal generation."""
        engine = SignalEngine()
        engine.register_strategy('ema_rsi')
        
        batch = [
            {
                'strategy_outputs': {'ema_rsi': {'signal': 'LONG'}},
                'symbol': 'BTCUSDT',
                'timeframe': '1h',
            },
            {
                'strategy_outputs': {'ema_rsi': {'signal': 'SHORT'}},
                'symbol': 'ETHUSDT',
                'timeframe': '4h',
            },
        ]
        
        signals = engine.generate_signal_batch(batch)
        
        assert len(signals) == 2
        assert signals[0].symbol == 'BTCUSDT'
        assert signals[1].symbol == 'ETHUSDT'
    
    def test_export_signals(self):
        """Test JSON export."""
        engine = SignalEngine()
        
        signal = engine.generate_signal(
            strategy_outputs={'ema_rsi': {'signal': 'LONG'}},
            symbol='BTCUSDT',
            timeframe='1h',
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'signals.json'
            engine.export_signals([signal], output_path)
            
            assert output_path.exists()
            
            with open(output_path) as f:
                data = json.load(f)
            
            assert data['num_signals'] == 1
            assert data['signals'][0]['direction'] == 'LONG'
    
    def test_no_actionable_signal(self):
        """Test FLAT signal (no trade)."""
        engine = SignalEngine()
        
        signal = engine.generate_signal(
            strategy_outputs={
                'ema_rsi': {'signal': 'FLAT'},
                'macd': {'signal': 'FLAT'},
            },
            symbol='BTCUSDT',
            timeframe='1h',
        )
        
        assert signal.direction == SignalDirection.FLAT
        assert not signal.is_actionable()


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_strategy_outputs(self):
        """Test with no strategy inputs."""
        engine = SignalEngine()
        
        signal = engine.generate_signal(
            strategy_outputs={},
            symbol='BTCUSDT',
            timeframe='1h',
        )
        
        assert signal.direction == SignalDirection.FLAT
    
    def test_invalid_regime(self):
        """Test with invalid regime string."""
        engine = SignalEngine()
        
        signal = engine.generate_signal(
            strategy_outputs={'ema_rsi': {'signal': 'LONG'}},
            symbol='BTCUSDT',
            timeframe='1h',
            regime='INVALID_REGIME',
        )
        
        assert signal.regime == RegimeType.NEUTRAL  # Falls back to default
    
    def test_low_conviction_default(self):
        """Test minimum conviction floor."""
        calc = ConfidenceCalculator()
        
        # Single strategy, low vol
        conviction = calc.compute_conviction(
            num_strategies=1,
            agreeing_count=1,
            volatility_percentile=5,  # Very low vol
        )
        
        # Should still meet minimum
        assert conviction >= calc.config['min_base_conviction']
