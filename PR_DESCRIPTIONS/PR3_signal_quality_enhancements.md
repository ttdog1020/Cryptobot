# PR#3: Signal Quality Enhancements

## Overview
Extends Trade Intelligence module with signal quality metrics to improve decision-making without modifying execution paths.

## Changes

### 1. Timeframe Confluence
- Added `timeframe_alignment_score` to TradeSignal (0.0-1.0)
- Computes agreement across multiple timeframes (5m, 15m, 1h, 4h, etc.)
- Optional via `timeframe_signals` parameter in SignalEngine.generate_signal()

### 2. Signal Freshness & Decay
- Added `age_seconds` field tracking signal age from optional timestamp
- Added `decayed_conviction` applying exponential half-life decay
- Configurable via `decay_half_life_seconds` (default: 900s = 15min)
- Helps downweight stale signals in multi-strategy aggregation

### 3. Confidence Buckets
- Added `confidence_bucket` field: LOW / MEDIUM / HIGH
- Configurable thresholds via `confidence_bucket_thresholds` (default: 0.4 / 0.7)
- Complements existing `confidence_category` (VERY_LOW...VERY_HIGH)
- Simpler 3-tier system for filtering/alerting

### 4. Enhanced Explanations
- Replaced `_build_rationale()` with `_generate_explanation()`
- Includes consensus, conviction, decay, timeframe alignment, regime, and risks
- Populates both `rationale` and `explanation` fields for backward compatibility
- Human-readable payload for dashboards/alerts

## Testing
- Added 4 new test cases covering each feature
- All 35 tests pass
- Safety suite validated (no execution paths modified)

## Backward Compatibility
- All new fields optional with safe defaults
- Existing code receives `None` or computed defaults (age_seconds=0, decayed_conviction=conviction)
- JSON serialization preserved
- No breaking changes to public API

## Configuration Examples

```python
# Multi-timeframe signals with decay
engine = SignalEngine(
    decay_half_life_seconds=900,  # 15min half-life
    confidence_bucket_thresholds={'low': 0.35, 'high': 0.65},
)

signal = engine.generate_signal(
    strategy_outputs={'ema_rsi': {'signal': 'LONG'}},
    symbol='BTCUSDT',
    timeframe='1h',
    timeframe_signals={'5m': 'LONG', '15m': 'LONG', '4h': 'SHORT'},
    signal_timestamp='2025-01-14T12:00:00+00:00',
)

# signal.timeframe_alignment_score = 0.666 (2/3 agree with primary)
# signal.decayed_conviction < signal.conviction (if aged)
# signal.confidence_bucket in ['LOW', 'MEDIUM', 'HIGH']
```

## Risk Assessment
**Risk Level:** Low

- Analysis-only module (no execution)
- Backward compatible defaults
- Config-driven behavior
- All safety gates intact
- Tests + safety suite pass

## Documentation
- Updated trade_intelligence/README.md with new features and examples
- Added CHANGELOG.md entry
- Inline docstrings for new methods

## Checklist
- [x] Tests pass (35/35)
- [x] Safety suite passes
- [x] Backward compatible
- [x] JSON-serializable
- [x] Config-driven
- [x] No secrets/API keys
- [x] Documentation updated
- [x] Analysis-only (no execution changes)
