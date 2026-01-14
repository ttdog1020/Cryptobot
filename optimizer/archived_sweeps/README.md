# Archived Parameter Sweeps

This directory contains standalone parameter optimization sweep scripts that are no longer actively used in the main optimization pipeline. They are preserved for historical reference and potential future re-use.

## Archived Scripts

### sweep_macd_params.py
- **Purpose:** Parameter sweep specifically for MACD-only strategy
- **Lines:** 269
- **Strategy Target:** `strategies/macd_only.py`
- **Status:** Standalone tool - superseded by `auto_optimizer.py` (Module 10)
- **Last Used:** Legacy optimization workflows
- **Reuse Path:** Can be adapted as template for strategy-specific sweeps

## Current Optimization Pipeline

Active optimization system:
- **Primary:** `auto_optimizer.py` - Module 10 comprehensive auto-optimization
- **Used By:** `run_live_multi.py`, backtest workflows
- **Configuration:** `strategy_profiles.json`
- **Analysis:** `performance_report.py`

## Why Archived?

`sweep_macd_params.py` was a targeted MACD parameter search that:
1. Predated the unified `auto_optimizer.py` system
2. Hardcodes MACD strategy (not flexible)
3. Is not imported by any active code
4. Functionality covered by generic `auto_optimizer.py`

## Usage

To run manually (for reference/testing):

```bash
cd optimizer/archived_sweeps
python sweep_macd_params.py
```

**Note:** May have hardcoded paths or outdated dependencies - verify before running.

## Related Files

- `auto_optimizer.py` - Current optimization (Module 10)
- `sweep_v3_params.py` - Active parameter sweep (in root, used by auto_optimizer)
- `rank_sweep_v3.py` - Utility to rank sweep results (in root)
- `performance_report.py` - Result analysis
- `strategy_profiles.json` - Strategy-specific configurations

## Future Considerations

If resurrecting legacy sweep patterns:
1. Extract reusable logic to `optimizer/sweep_strategies.py`
2. Make strategy selection configurable
3. Integrate with `auto_optimizer.py` as optional backend
4. Add tests in `tests/test_param_search.py`

Ref: TECH_DEBT_REPORT.md Section 1.1
