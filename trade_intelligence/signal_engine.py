"""
Trade Signal Engine

Main orchestrator for signal generation and aggregation.
Combines strategy outputs, confidence scoring, risk analysis.
"""

from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import logging

from .signal_model import TradeSignal, SignalDirection, RegimeType, RiskFlags
from .confidence import ConfidenceCalculator, DEFAULT_CONFIDENCE_CONFIG
from .risk_context import RiskContextAnalyzer, RiskContext
from .aggregation import SignalAggregator, StrategyOutputFormat

logger = logging.getLogger(__name__)


class SignalEngine:
    """
    Core trade signal generation engine.
    
    Workflow:
    1. Ingest multiple strategy outputs
    2. Normalize via adapters
    3. Aggregate direction and agreement
    4. Compute conviction score
    5. Analyze risk context
    6. Produce JSON-serializable TradeSignal
    """
    
    def __init__(
        self,
        confidence_config: Optional[Dict[str, float]] = None,
        vol_spike_threshold: float = 1.5,
        drawdown_threshold: float = 0.10,
    ):
        """
        Initialize signal engine.
        
        Args:
            confidence_config: Override DEFAULT_CONFIDENCE_CONFIG
            vol_spike_threshold: Volatility spike multiplier
            drawdown_threshold: Drawdown threshold (e.g., 0.10 = 10%)
        """
        self.aggregator = SignalAggregator()
        self.confidence_calc = ConfidenceCalculator(confidence_config)
        self.risk_analyzer = RiskContextAnalyzer(
            vol_spike_threshold=vol_spike_threshold,
            drawdown_threshold=drawdown_threshold,
        )
    
    def register_strategy(
        self,
        name: str,
        format_type: StrategyOutputFormat = StrategyOutputFormat.TRADE_INTENT,
    ):
        """Register a strategy."""
        self.aggregator.register_strategy(name, format_type)
    
    def generate_signal(
        self,
        strategy_outputs: Dict[str, Any],
        symbol: str,
        timeframe: str,
        regime: Optional[str] = None,
        volatility_percentile: Optional[float] = None,
        current_volatility: Optional[float] = None,
        volatility_sma: Optional[float] = None,
        volume: Optional[float] = None,
        volume_sma: Optional[float] = None,
        current_equity: Optional[float] = None,
        peak_equity: Optional[float] = None,
    ) -> TradeSignal:
        """
        Generate a single trade signal.
        
        Args:
            strategy_outputs: {strategy_name: output, ...}
            symbol: Trading pair (e.g., BTCUSDT)
            timeframe: Candle timeframe (e.g., 1h)
            regime: Market regime (TRENDING/RANGING/BREAKOUT/NEUTRAL)
            volatility_percentile: Current vol as percentile (0-100)
            current_volatility: Current volatility measure
            volatility_sma: Volatility SMA
            volume: Current candle volume
            volume_sma: Volume SMA
            current_equity: Current portfolio value
            peak_equity: Peak portfolio equity
        
        Returns:
            TradeSignal object
        """
        # Step 1: Aggregate strategies
        agg_result = self.aggregator.aggregate(strategy_outputs)
        
        direction_str = agg_result['direction']
        direction = SignalDirection[direction_str]
        num_strategies = agg_result['num_strategies']
        agreeing_count = agg_result['agreeing']
        agreement_ratio = agg_result['agreement_ratio']
        
        # Step 2: Compute conviction
        conviction = self.confidence_calc.compute_conviction(
            num_strategies=num_strategies,
            agreeing_count=agreeing_count,
            volatility_percentile=volatility_percentile,
            win_rate=None,  # Could add historical win rate later
        )
        
        # Step 3: Analyze risk
        risk_context = self.risk_analyzer.analyze(
            current_volatility=current_volatility,
            volatility_sma=volatility_sma,
            volume=volume,
            volume_sma=volume_sma,
            current_equity=current_equity,
            peak_equity=peak_equity,
            num_strategies=num_strategies,
            agreeing_count=agreeing_count,
        )
        
        # Step 4: Parse regime
        regime_type = RegimeType.NEUTRAL
        if regime:
            try:
                regime_type = RegimeType[regime.upper()]
            except KeyError:
                logger.warning(f"Unknown regime: {regime}")
        
        # Step 5: Build signal
        signal = TradeSignal(
            direction=direction,
            conviction=conviction,
            symbol=symbol,
            timeframe=timeframe,
            regime=regime_type,
            num_strategies=num_strategies,
            agreeing_strategies=agreeing_count,
            agreement_ratio=agreement_ratio,
            risk_flags=RiskFlags(
                volatility_spike=risk_context.volatility_spike,
                low_liquidity=risk_context.low_liquidity,
                drawdown_risk=risk_context.drawdown_risk,
                conflicting_signals=risk_context.conflicting_signals,
            ),
            strategy_names=list(strategy_outputs.keys()),
            volatility_percentile=volatility_percentile,
        )
        
        # Step 6: Generate rationale
        signal.rationale = self._generate_rationale(signal, agg_result)
        
        return signal
    
    def _generate_rationale(
        self,
        signal: TradeSignal,
        agg_result: Dict[str, Any],
    ) -> str:
        """Generate human-readable rationale for signal."""
        rationale_parts = []
        
        # Direction + agreement
        if signal.direction == SignalDirection.FLAT:
            rationale_parts.append("No clear consensus")
        else:
            rationale_parts.append(
                f"{signal.direction.value} signal from "
                f"{signal.agreeing_strategies}/{signal.num_strategies} strategies"
            )
        
        # Confidence
        rationale_parts.append(
            f"conviction {signal.conviction:.1%} ({signal.confidence_category.value})"
        )
        
        # Risk flags
        risk_flags = []
        if signal.risk_flags.volatility_spike:
            risk_flags.append("vol↑")
        if signal.risk_flags.low_liquidity:
            risk_flags.append("low-liq")
        if signal.risk_flags.drawdown_risk:
            risk_flags.append("dd-risk")
        if signal.risk_flags.conflicting_signals:
            risk_flags.append("conflict")
        
        if risk_flags:
            rationale_parts.append(f"[{','.join(risk_flags)}]")
        
        # Regime
        if signal.regime != RegimeType.NEUTRAL:
            rationale_parts.append(f"in {signal.regime.value.lower()}")
        
        return " | ".join(rationale_parts)
    
    def generate_signal_batch(
        self,
        batch: List[Dict[str, Any]],
    ) -> List[TradeSignal]:
        """
        Generate signals for a batch of symbol/timeframe combinations.
        
        Args:
            batch: List of dicts with keys:
                - strategy_outputs: dict
                - symbol: str
                - timeframe: str
                - (optional) regime, volatility_percentile, etc.
        
        Returns:
            List of TradeSignal objects
        """
        signals = []
        for params in batch:
            try:
                signal = self.generate_signal(**params)
                signals.append(signal)
            except Exception as e:
                logger.error(f"Error generating signal for {params}: {e}")
        
        return signals
    
    def export_signals(
        self,
        signals: List[TradeSignal],
        output_path: Path,
    ) -> None:
        """
        Export signals to JSON file.
        
        Args:
            signals: List of TradeSignal objects
            output_path: Path to output JSON file
        """
        data = {
            'timestamp': signals[0].timestamp if signals else None,
            'num_signals': len(signals),
            'signals': [s.to_dict() for s in signals],
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported {len(signals)} signals to {output_path}")
