# PR7: Rollback Safeguards for Evolution Engine

## Problem
Auto-evolution can apply bad parameter updates that persist, degrading live trading performance. No way to revert or validate updates before applying.

## Solution
Implement `RollbackManager` + `RollbackValidator` to track parameter history, validate updates, and enable fast rollback to known-good state.

## Architecture

### Core Classes
- **ProfileVersion**: Snapshot with parameters, metrics, change tracking, SHA256 hash
- **RollbackManager**: Maintain versioned history (JSON-persisted), load/save/rollback operations
- **RollbackValidator**: Pre-apply validation with configurable safety thresholds
- **safe_apply_evolution()**: Integration function for EvolutionEngine

### Validation Checks (in order)
1. **Outlier Detection**: Reject negative stop_loss/take_profit/position_size
2. **Chaos Detection**: Reject if >50% of parameters change at once
3. **Parameter Drift**: Reject if any param changes >N% (default 50%)
4. **Metrics Improvement**: Reject if improvement <N% (default 5%)

### Version Tracking
- Compute SHA256 hash of parameter dict for quick comparison
- Track all changes from previous version with % deltas
- Store git commit hash if available for audit trail
- JSON history per symbol/strategy with full metadata

## Testing
- 20 tests covering all classes and edge cases
- ProfileVersion serialization/deserialization roundtrips
- RollbackManager version history, tracking, rollback
- RollbackValidator all 4 safety checks
- safe_apply_evolution happy/sad paths
- Error handling (corrupted files, empty history, OOB indices)

## Integration
```python
from optimizer.rollback_manager import RollbackManager, RollbackValidator, safe_apply_evolution

manager = RollbackManager('config/profile_versions')
validator = RollbackValidator(drift_tolerance_pct=50.0, improvement_threshold_pct=5.0)

success, msg = safe_apply_evolution(
    symbol="BTCUSDT",
    strategy="scalping_ema_rsi",
    old_params={"ema_period": 12, "rsi_threshold": 30},
    new_params={"ema_period": 14, "rsi_threshold": 28},
    old_metrics={"return_pct": 5.0, "sharpe": 1.5},
    new_metrics={"return_pct": 7.5, "sharpe": 1.8},
    manager=manager,
    validator=validator,
    reason="Evolution run 2025-01-15"
)

if success:
    print(f"Evolution applied, new state version: {version_index}")
else:
    print(f"Evolution rejected: {msg}")
```

## Risk Assessment
- **Risk Level**: MED (High impact on evolution safety)
- **Impact**: HIGH (Prevents bad parameter mutations from persisting)
- **Backward Compatibility**: ✅ No breaking changes
- **Safety**: ✅ No live trading modifications
- **Testing**: ✅ 20 tests pass

## Files
- `optimizer/rollback_manager.py` - 400+ LOC
- `tests/test_rollback_manager.py` - 320+ LOC
- No config changes required
