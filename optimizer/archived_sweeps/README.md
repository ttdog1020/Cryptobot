# Archived Parameter Sweeps

This directory contains standalone parameter optimization sweep scripts that were used for strategy development but are not integrated into the main optimization pipeline.

## Archived Scripts

### sweep_macd_params.py
- **Purpose:** Parameter sweep specifically for MACD-only strategy
- **Lines:** 269
- **Strategy:** `strategies/macd_only.py`
- **Status:** Standalone tool - not integrated with `auto_optimizer.py`
- **Created:** Pre-Module 10 (auto optimizer)
- **Usage:** Manual parameter grid search for MACD indicator settings

### rank_sweep_v3.py
- **Purpose:** Post-processing tool for `sweep_v3_params.py` results
- **Lines:** 14
- **Status:** Utility for ranking sweep results
- **Usage:** Analyzes output from sweep_v3 and generates ranked report

## Current Optimization Pipeline

The **active** optimization system is:
- **Primary:** `auto_optimizer.py` - Module 10 auto-optimization system
- **Integration:** Uses `sweep_v3_params.py` (still in root)
- **Strategy Profiles:** Loads from `strategy_profiles.json`
- **Output:** `performance_report.py` for analysis

## Why Archived?

These scripts represent **legacy** optimization approaches:

1. **sweep_macd_params.py:** MACD-specific sweep superseded by generic `auto_optimizer.py`
2. **rank_sweep_v3.py:** Post-processor for sweep_v3 results (utility, not core workflow)

They are preserved for:
- Historical reference
- Potential re-use for targeted parameter studies
- Comparison with new optimization methods

## Usage

To run manually (from repo root):

```bash
# MACD-specific parameter sweep
python optimizer/archived_sweeps/sweep_macd_params.py

# Rank sweep_v3 results
python optimizer/archived_sweeps/rank_sweep_v3.py
```

**Note:** These scripts may have hardcoded paths or dependencies - review before running.

## Migration Path

If integrating these approaches into the main pipeline:

1. Extract sweep logic into `optimizer/sweep_strategies.py`
2. Add strategy-specific sweep configs to `strategy_profiles.json`
3. Update `auto_optimizer.py` to support custom sweep definitions
4. Add tests in `tests/test_param_search.py`

## Related Files

- `auto_optimizer.py` - Current optimization system (Module 10)
- `sweep_v3_params.py` - Active sweep used by auto-optimizer
- `performance_report.py` - Result analysis
- `strategy_profiles.json` - Strategy-specific configs
- `optimizer/` - Main optimization module directory

## Maintenance

- Keep for reference unless duplicate functionality confirmed in main pipeline
- Update this README when adding new archived sweeps
- Consider deletion only if zero value for future research
