# Archived Validators

This directory contains one-time validation scripts that were used during specific module development or bug fixes. They are preserved for historical reference and potential re-use if similar issues arise.

## Archived Scripts

### verify_config_backtest.py
- **Purpose:** Validated Module 29 (Config-Driven Backtest) implementation
- **Created:** December 2024
- **Status:** Completed - config_backtest.py now has full test coverage
- **Reuse:** Can serve as integration test template

### verify_flatten_shutdown.py
- **Purpose:** Validated flatten-on-shutdown feature for safe position exit
- **Created:** December 2024
- **Status:** Completed - now covered by `test_flatten_shutdown.py`
- **Reuse:** Demonstrates safe shutdown testing patterns

### verify_module_27_patches.py
- **Purpose:** Validated Module 27 patches for multi-session improvements
- **Created:** December 2024
- **Status:** Completed - patches integrated and tested
- **Reuse:** Multi-session validation examples

### verify_symbol_fix.py
- **Purpose:** Validated symbol propagation fix across orchestrator/execution
- **Created:** December 2024
- **Status:** Completed - fix merged and tested in main suite
- **Reuse:** Symbol routing test patterns

## Usage

These scripts are **not** run as part of the regular test suite. To run manually:

```bash
# From repo root
python validation/archived_validators/verify_config_backtest.py
```

## Maintenance

- These files are preserved for documentation/reference only
- Do **not** delete unless you're certain the validation is no longer relevant
- If updating related modules, consider whether these validators need updates
- When creating new validators, follow the `verify_*.py` naming convention

## Migration to Permanent Tests

If a verification pattern proves valuable long-term:

1. Extract reusable test logic
2. Add to appropriate `tests/test_*.py` file
3. Update this README to note migration
4. Keep original for reference

## Related Documentation

- `tests/` - Permanent test suite
- `validation/safety_suite.py` - Core safety validations
- `TECH_DEBT_REPORT.md` - Module-level cleanup tracking
