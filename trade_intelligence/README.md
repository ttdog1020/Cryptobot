# Trade Intelligence Module

**Status:** Analysis-only, no execution  
**Purpose:** Convert strategy outputs into structured, explainable trade signals

## Overview

Trade Intelligence provides a unified framework for aggregating signals from multiple strategies without refactoring strategy code. It produces JSON-serializable `TradeSignal` objects with:

- **Direction**: LONG / SHORT / FLAT
- **Conviction**: 0.0-1.0 confidence score
- **Regime context**: TRENDING / RANGING / BREAKOUT / NEUTRAL
- **Risk flags**: Volatility spikes, liquidity issues, drawdown risk, conflicting signals
- **Strategy agreement**: How many strategies agree, agreement ratio
- **Rationale**: Human-readable explanation

## Key Features

### 1. Multi-Strategy Aggregation
- Ingest outputs from any number of strategies
- Support multiple output formats via thin adapters (no strategy refactoring)
- Normalize to standard signal format

### 2. Conviction Scoring
- Configurable weighting: strategy agreement (60%), volatility norm (20%), historical (20%)
- Automatic confidence categorization: VERY_HIGH / HIGH / MEDIUM / LOW / VERY_LOW
- Floor at minimum conviction to avoid extreme low scores

### 3. Risk Context Detection
- **Volatility spike**: Current vol > 1.5x avg
- **Low liquidity**: Current volume < 50% avg
- **Drawdown risk**: Portfolio down > 10%
- **Conflicting signals**: >30% strategy dissent

### 4. JSON Export
All signals are JSON-serializable for CI integration, dashboards, Discord alerts, etc.

## Architecture

```
trade_intelligence/
├── __init__.py                    # Public API
├── signal_model.py               # TradeSignal, SignalDirection, etc.
├── signal_engine.py              # Main orchestrator
├── confidence.py                 # Conviction scoring
├── risk_context.py               # Risk detection
├── aggregation.py                # Multi-strategy combination
└── README.md                     # This file
```

## Usage

### Basic: Single Strategy

```python
from trade_intelligence import SignalEngine

engine = SignalEngine()
engine.register_strategy('ema_rsi', format_type='TradeIntent')

signal = engine.generate_signal(
    strategy_outputs={'ema_rsi': {'signal': 'LONG', 'metadata': {...}}},
    symbol='BTCUSDT',
    timeframe='1h',
)

print(signal)
# TradeSignal(BTCUSDT 1h @ ...): LONG conviction=0.60 (HIGH) regime=NEUTRAL agreement=100.0%

print(signal.to_dict())
# {'direction': 'LONG', 'conviction': 0.600, 'confidence_category': 'HIGH', ...}
```

### Advanced: Multi-Strategy Consensus

```python
engine = SignalEngine()
engine.register_strategy('ema_rsi')
engine.register_strategy('macd')
engine.register_strategy('bb_squeeze')

signal = engine.generate_signal(
    strategy_outputs={
        'ema_rsi': {'signal': 'LONG'},
        'macd': {'signal': 'LONG'},
        'bb_squeeze': {'signal': 'FLAT'},
    },
    symbol='BTCUSDT',
    timeframe='1h',
    regime='TRENDING',
    volatility_percentile=45,  # Mid-range volatility
)

# 2/3 strategies agree
# conviction = 0.6 * (2/3) + 0.2 * vol_norm(45) + 0.2 * hist
```

### With Risk Context

```python
signal = engine.generate_signal(
    strategy_outputs={'ema_rsi': {'signal': 'LONG'}},
    symbol='BTCUSDT',
    timeframe='1h',
    current_volatility=1.2,
    volatility_sma=0.8,  # Spike detected!
    volume=1000,
    volume_sma=2000,     # Low liquidity!
)

print(signal.risk_flags)
# RiskFlags(
#   volatility_spike=True,
#   low_liquidity=True,
#   drawdown_risk=False,
#   conflicting_signals=False
# )

print(signal.is_actionable(min_conviction=0.5))
# True or False depending on conviction
```

### Batch Generation

```python
batch = [
    {
        'strategy_outputs': {'ema_rsi': {'signal': 'LONG'}},
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
    },
    {
        'strategy_outputs': {'macd': {'signal': 'SHORT'}},
        'symbol': 'ETHUSDT',
        'timeframe': '4h',
    },
]

signals = engine.generate_signal_batch(batch)

# Export to JSON
engine.export_signals(signals, Path('signals.json'))
```

## Configuration

### Confidence Scoring

```python
config = {
    'weight_agreement': 0.6,           # How much agreement matters
    'weight_volatility': 0.2,          # How much vol normalization matters
    'weight_historical': 0.2,          # Historical win rate
    'min_base_conviction': 0.3,        # Floor conviction
    'agreement_decay': 0.05,           # Penalty per missing strategy
}

engine = SignalEngine(confidence_config=config)
```

### Risk Detection

```python
engine = SignalEngine(
    vol_spike_threshold=1.5,           # Current vol > 1.5x avg = spike
    drawdown_threshold=0.10,           # >10% drawdown = risk
)
```

## Integration Points

### With Strategy Outputs

Trade Intelligence expects strategy outputs in one of these formats:

1. **TradeIntent** (default): `{'signal': 'LONG'|'SHORT'|'FLAT', 'metadata': {...}}`
2. **SignalDict**: `{'signal': '...', 'confidence': 0.5}`
3. **Boolean**: `True` (LONG), `False` (FLAT)

Register the format when you register the strategy:

```python
engine.register_strategy('my_strategy', format_type=StrategyOutputFormat.BOOLEAN)
```

### With Dashboards / Alerts

Export signals to JSON:

```python
engine.export_signals(signals, Path('signals.json'))

# Use in Discord bot, web dashboard, etc.
with open('signals.json') as f:
    data = json.load(f)
    for signal_dict in data['signals']:
        # Send to Discord, log, filter, etc.
        pass
```

### With CI/CD

```python
# In CI script
signals = engine.generate_signal_batch(...)

actionable = [s for s in signals if s.is_actionable(min_conviction=0.6)]

if len(actionable) == 0:
    print("No high-confidence signals")
    exit(0)
else:
    print(f"Found {len(actionable)} signals")
    exit(1)  # Trigger alert in CI
```

## Design Principles

1. **Analysis-only**: No execution, no order placement, read-only
2. **Non-invasive**: Strategies stay unchanged; adapters normalize outputs
3. **Explainable**: Every signal has rationale + risk flags
4. **JSON-native**: All outputs are JSON-serializable
5. **Configurable**: Weights, thresholds, formats all customizable
6. **Defensive**: Graceful handling of missing/invalid inputs

## Testing

```bash
# Run unit tests
pytest tests/test_trade_intelligence/ -v

# Check coverage
pytest tests/test_trade_intelligence/ --cov=trade_intelligence --cov-report=html
```

Expected coverage: >80%

## Future Extensions

- Historical backtest stats per strategy (for weighted conviction)
- Regime detection from live OHLCV
- Correlation analysis (are strategies truly independent?)
- Performance dashboard integration
- Discord/Slack webhook formatting
- A/B testing framework for confidence configs

## References

- [Signal Model](signal_model.py): Core data structures
- [Signal Engine](signal_engine.py): Main orchestrator
- [Confidence](confidence.py): Conviction scoring
- [Risk Context](risk_context.py): Risk detection
- [Aggregation](aggregation.py): Multi-strategy combination

---

**Owner:** Autonomous Development  
**Status:** Analysis-only, no trading logic  
**Last Updated:** January 14, 2026
