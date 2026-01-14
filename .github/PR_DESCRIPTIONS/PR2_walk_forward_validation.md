# PR2: Add Walk-Forward Validation Harness with Overfitting Detection

## Summary
Comprehensive walk-forward analysis framework to detect overfitting and parameter drift, with configurable thresholds and integration hooks for auto_optimizer. Enables robust parameter validation across multiple train/test windows.

## Type
- [x] New Feature
- [x] Enhancement
- [ ] Bug Fix
- [ ] Documentation

## Risk Level
**LOW** - Pure analysis module, no trading logic, comprehensive tests, configurable with safe defaults

## Changes

### New Module: `backtests/walk_forward.py` (~850 LOC)
- **WalkForwardValidator** class for orchestrating walk-forward analysis
- **WindowGenerator** with 3 strategies: rolling, anchored, fixed_gap
- **WalkForwardWindow** class for train/test window pairs
- **DriftMonitor** for parameter stability tracking across windows
- Support for parameter bounds and drift penalties
- Overfitting penalty computation with configurable tolerance
- Summary statistics and DataFrame export for analysis
- Factory function: `create_walk_forward_from_config()`

### New Module: `validation/overfitting_check.py` (~350 LOC)
- **detect_overfitting**: Binary overfitting detection (train >> test)
- **compute_overfitting_penalty**: Quantify overfitting impact for fitness
- **stability_score**: Measure performance consistency across windows
- **degradation_ratio**: Average train-to-test degradation analysis
- **is_robust_parameters**: Check parameter stability (drift detection)
- **OverfittingReport** class for detailed human-readable analysis
- **validate_walk_forward_results**: Quality checks on results

### New Config: `config/walk_forward.yaml`
- Window strategy and sizing (rolling, anchored, fixed_gap)
- Overfitting thresholds and severity classification
- Parameter drift monitoring and bounds enforcement
- Stability requirements and degradation limits
- Veto rules for parameter rejection
- Integration hooks for auto_optimizer
- Optional HTML reporting setup

### New Tests: `tests/test_walk_forward.py` (~450 LOC)
- **TestWalkForwardWindow**: Window creation and duration calculations
- **TestWindowGenerator**: All 3 window strategies with edge cases
- **TestDriftMonitor**: Parameter drift and bounds checking
- **TestWalkForwardValidator**: Main validator functionality
- **TestOverfittingDetection**: Penalty and detection functions
- **TestCreateFromConfig**: Config factory function
- **Total:** 20+ unit tests with comprehensive coverage

## Key Features

✅ **Multiple window strategies** for flexible analysis
✅ **Parameter drift detection** with configurable bounds enforcement
✅ **Configurable overfitting thresholds** and penalties
✅ **Stability scoring** and degradation analysis
✅ **Integration-ready** for auto_optimizer fitness functions
✅ **Comprehensive test coverage** (20+ tests)
✅ **Config-driven parameters** via walk_forward.yaml

## Architecture

### Component Flow
1. **WindowGenerator** creates train/test splits based on strategy
2. **WalkForwardValidator** orchestrates the analysis across windows
3. **DriftMonitor** tracks parameters and detects instability
4. **OverfittingReport** provides human-readable analysis
5. **Penalty functions** enable integration into optimizer fitness

### Window Strategies

#### Rolling Windows
- Sliding window with no overlap
- Fixed train/test sizes
- Good for detecting regime-specific overfitting

#### Anchored Windows
- Expanding train window (fixed start)
- Rolling test window
- Good for testing parameter stability as data grows

#### Fixed-Gap Windows
- Gap between train and test periods
- Simulates real-world deployment delay
- Good for testing forward-looking robustness

## Files Changed
- `backtests/walk_forward.py` - New module (+850 LOC)
- `validation/overfitting_check.py` - New module (+350 LOC)
- `tests/test_walk_forward.py` - New tests (+450 LOC)
- `config/walk_forward.yaml` - New config (+90 LOC)

**Net Change:** ~1,740 LOC added (all new, no modifications)

## Testing

### Run All Tests
```bash
# Full test suite
pytest tests/test_walk_forward.py -v

# Individual test classes
pytest tests/test_walk_forward.py::TestWindowGenerator -v
pytest tests/test_walk_forward.py::TestDriftMonitor -v
pytest tests/test_walk_forward.py::TestOverfittingDetection -v
pytest tests/test_walk_forward.py::TestWalkForwardValidator -v
```

### Manual Testing
```python
from backtests.walk_forward import WalkForwardValidator, WindowStrategy
import pandas as pd

# Create sample data
dates = pd.date_range('2025-01-01', periods=180, freq='D')
data = pd.DataFrame({
    'close': range(100, 280),
    'volume': [1000] * 180
}, index=dates)

# Initialize validator
validator = WalkForwardValidator(
    data=data,
    window_strategy=WindowStrategy.ROLLING,
    train_window_days=30,
    test_window_days=7
)

print(f"Generated {len(validator.windows)} windows")
```

## Usage Example

### Basic Walk-Forward Analysis
```python
from backtests.walk_forward import WalkForwardValidator, WindowStrategy

validator = WalkForwardValidator(
    data=historical_df,
    window_strategy=WindowStrategy.ROLLING,
    train_window_days=30,
    test_window_days=7
)

# For each window, run strategy and record results
for window in validator.windows:
    train_data = validator.get_window_data(window, split='train')
    test_data = validator.get_window_data(window, split='test')
    
    # Run backtest on both periods
    train_metrics = run_backtest(train_data, params)
    test_metrics = run_backtest(test_data, params)
    
    # Record results
    validator.record_window_result(
        window.window_id,
        params,
        train_metrics,
        test_metrics
    )

# Analyze results
stats = validator.summary_statistics()
print(f"Avg Train Sharpe: {stats['avg_train_sharpe']:.3f}")
print(f"Avg Test Sharpe: {stats['avg_test_sharpe']:.3f}")
print(f"Overfitting Penalty: {stats['avg_overfitting_penalty']:.3f}")
```

### Integration with Optimizer
```python
from validation.overfitting_check import compute_overfitting_penalty

# During fitness evaluation
train_sharpe = 1.5
test_sharpe = 0.8

penalty = compute_overfitting_penalty(
    train_sharpe,
    test_sharpe,
    tolerance=0.3,
    penalty_scale=1.0
)

# Adjust fitness
adjusted_fitness = train_sharpe - penalty
```

## Validation Checklist
- [x] All tests pass locally (20+ tests)
- [x] No breaking changes to existing APIs
- [x] Backward compatible (all new code)
- [x] Config-driven with safe defaults
- [x] Proper error handling for edge cases
- [x] Comprehensive test coverage
- [x] Documentation in docstrings

## Safety Check
- [x] No live trading paths
- [x] No secrets committed
- [x] No changes to core trading logic
- [x] Pure analysis/validation module
- [x] No impact on existing backtests

## Acceptance Criteria
- [x] Can generate rolling/anchored/fixed-gap windows
- [x] Tracks parameter drift across windows
- [x] Computes overfitting penalties
- [x] Provides summary statistics
- [x] Configurable via walk_forward.yaml
- [x] Integration hooks for auto_optimizer
- [x] Comprehensive test coverage

## Benefits

### For Strategy Development
- Detect overfitting before live deployment
- Validate parameter stability across time
- Identify regime-dependent strategies
- Quantify generalization performance

### For Auto-Optimizer
- Penalty functions for fitness adjustment
- Veto rules for parameter rejection
- Drift monitoring for evolution safety
- Rollback safeguards integration

### For Risk Management
- Early warning for degrading strategies
- Robustness scoring for confidence
- Out-of-sample validation automated
- Regime analysis support

## Integration Plan

### Phase 1 (This PR)
- Core walk-forward infrastructure
- Overfitting detection and penalties
- Config and tests

### Phase 2 (Future PR)
- Auto-optimizer integration
- Fitness function penalty incorporation
- Automated veto rules

### Phase 3 (Future PR)
- HTML report generation
- Regime classification integration
- Parameter evolution tracking

## Related Issues
- Supports overfitting resistance (backlog item #2)
- Foundational for parameter drift constraints (backlog item #5)
- Enables rollback safeguards (backlog item #7)

## Merge Strategy
- [x] Enable auto-merge (LOW risk)
- [x] Squash commits on merge
- Target: `staging` branch

## Post-Merge Actions
- Document integration examples
- Add walk-forward validation to optimization workflow
- Monitor for edge cases in production

---

**Auto-merge:** ✅ Enabled (LOW risk, pure analysis, comprehensive tests)
