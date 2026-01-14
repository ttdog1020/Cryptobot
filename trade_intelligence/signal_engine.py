"""
Trade Signal Engine

Main orchestrator for signal generation and aggregation.
Combines strategy outputs, confidence scoring, risk analysis.
"""

from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import logging
from datetime import datetime, timezone

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
        decay_half_life_seconds: Optional[float] = 900.0,
        confidence_bucket_thresholds: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize signal engine.
        
        Args:
            confidence_config: Override DEFAULT_CONFIDENCE_CONFIG
            vol_spike_threshold: Volatility spike multiplier
            drawdown_threshold: Drawdown threshold (e.g., 0.10 = 10%)
            decay_half_life_seconds: Optional half-life (seconds) for conviction decay; None to disable decay
            confidence_bucket_thresholds: Optional thresholds for confidence buckets (low/high)
        """
        self.aggregator = SignalAggregator()
        self.confidence_calc = ConfidenceCalculator(confidence_config)
        self.risk_analyzer = RiskContextAnalyzer(
            vol_spike_threshold=vol_spike_threshold,
            drawdown_threshold=drawdown_threshold,
        )
        self.decay_half_life_seconds = decay_half_life_seconds
        self.confidence_bucket_thresholds = confidence_bucket_thresholds
    
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
        timeframe_signals: Optional[Dict[str, str]] = None,
        signal_timestamp: Optional[str] = None,
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

        # Step 2b: Apply decay based on signal age
        age_seconds = self._compute_age_seconds(signal_timestamp)
        decayed_conviction = self._apply_decay(conviction, age_seconds)
        
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
            timeframe_alignment_score=self._compute_timeframe_alignment(
                direction,
                timeframe_signals,
            ),
            age_seconds=age_seconds,
            decayed_conviction=decayed_conviction,
            confidence_bucket_thresholds=self.confidence_bucket_thresholds,
        )
        
        # Step 6: Generate rationale
        explanation = self._generate_explanation(signal, agg_result)
        signal.rationale = explanation
        signal.explanation = explanation
        
        return signal

    def _compute_timeframe_alignment(
        self,
        primary_direction: SignalDirection,
        timeframe_signals: Optional[Dict[str, str]] = None,
    ) -> Optional[float]:
        """Compute agreement across multiple timeframes.
        
        Args:
            primary_direction: Direction of the aggregated signal
            timeframe_signals: Optional mapping timeframe -> direction string
        
        Returns:
            Alignment score in [0,1], or None if no data.
        """
        if not timeframe_signals:
            return None

        directions = []
        for tf_dir in timeframe_signals.values():
            try:
                directions.append(SignalDirection[tf_dir])
            except Exception:
                continue
        if not directions:
            return None

        total = len(directions)
        if total == 0:
            return None

        matches = sum(1 for d in directions if d == primary_direction)
        return round(matches / total, 3)

    def _compute_age_seconds(self, signal_timestamp: Optional[str]) -> float:
        """Compute age in seconds from provided timestamp to now."""
        if not signal_timestamp:
            return 0.0
        try:
            parsed = datetime.fromisoformat(signal_timestamp.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            return max(0.0, (now - parsed).total_seconds())
        except Exception:
            return 0.0

    def _apply_decay(self, conviction: float, age_seconds: float) -> float:
        """Apply exponential decay to conviction based on age."""
        if self.decay_half_life_seconds is None or self.decay_half_life_seconds <= 0:
            return conviction
        decay_factor = 0.5 ** (age_seconds / self.decay_half_life_seconds)
        return max(0.0, conviction * decay_factor)
    
    def _generate_explanation(
        self,
        signal: TradeSignal,
        agg_result: Dict[str, Any],
    ) -> str:
        """Generate human-readable explanation for signal."""
        parts = []

        # Strategy agreement
        if signal.direction == SignalDirection.FLAT:
            parts.append("Consensus: FLAT (no clear bias)")
        else:
            parts.append(
                f"Consensus: {signal.direction.value} from {signal.agreeing_strategies}/{signal.num_strategies}"
            )

        # Conviction + decay
        base = f"Conviction: {signal.conviction:.2f} ({signal.confidence_category.value})"
        if signal.decayed_conviction is not None and signal.decayed_conviction != signal.conviction:
            base += f" → decayed {signal.decayed_conviction:.2f}"
        parts.append(base)

        # Timeframe alignment
        if signal.timeframe_alignment_score is not None:
            parts.append(f"TF alignment: {signal.timeframe_alignment_score:.0%}")

        # Regime
        if signal.regime != RegimeType.NEUTRAL:
            parts.append(f"Regime: {signal.regime.value.lower()}")

        # Risk flags
        risk_flags = []
        if signal.risk_flags.volatility_spike:
            risk_flags.append("vol spike")
        if signal.risk_flags.low_liquidity:
            risk_flags.append("low liq")
        if signal.risk_flags.drawdown_risk:
            risk_flags.append("drawdown")
        if signal.risk_flags.conflicting_signals:
            risk_flags.append("conflict")
        if risk_flags:
            parts.append(f"Risks: {', '.join(risk_flags)}")
        else:
            parts.append("Risks: none detected")

        # Age
        if signal.age_seconds is not None and signal.age_seconds > 0:
            parts.append(f"Age: {signal.age_seconds:.0f}s")

        return " | ".join(parts)
    
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
