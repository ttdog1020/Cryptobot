# Archived Verification Scripts

This directory contains one-time verification scripts used to validate specific module implementations. These scripts were run during development to ensure correctness but are no longer needed for regular operations.

## Archived Scripts

### verify_symbol_fix.py (157 lines)
**Module:** Symbol Propagation Fix  
**Purpose:** Verify that ExecutionEngine correctly propagates symbols through the trade pipeline  
**Status:** ✅ Verified and fixed in SYMBOL_PROPAGATION_FIX.md  
**Archived:** January 14, 2026

**Key tests:**
- UNKNOWN symbol rejection
- Symbol propagation through PaperTrader
- Symbol recording in trade logs

### verify_module_27_patches.py (231 lines)
**Module:** MODULE_27 Accounting Patches  
**Purpose:** Verify mandatory patches for balance accounting, kill switch, and ExecutionResult  
**Status:** ✅ All patches verified in MODULE_27_COMPLETE.md  
**Archived:** January 14, 2026

**Key tests:**
- apply_trade_result helper function
- Kill switch peak_equity tracking
- ExecutionResult.filled_quantity attribute
- CSV logs with realized_pnl, balance, equity

### verify_flatten_shutdown.py (217 lines)
**Module:** Flatten-on-Shutdown  
**Purpose:** Verify that PaperTrader correctly closes all positions on shutdown  
**Status:** ✅ Verified and documented in FLATTEN_ON_SHUTDOWN.md  
**Archived:** January 14, 2026

**Key tests:**
- close_all_positions() functionality
- Multi-position flattening
- Trade logging on shutdown
- Balance reconciliation

### verify_config_backtest.py (224 lines)
**Module:** Configuration-Driven Backtest Runner  
**Purpose:** Verify that config_backtest module imports, loads configs, and runs backtests  
**Status:** ✅ Verified in CONFIG_BACKTEST.md  
**Archived:** January 14, 2026

**Key tests:**
- Module imports
- Configuration loading
- Component initialization
- Cash+equity model integration
- Basic backtest execution

## Why Archived?

These scripts served their purpose during module development:
- Each verified a specific feature or fix
- All features are now covered by the automated test suite (`tests/`)
- Keeping them in root cluttered the project structure
- They may be useful for reference when implementing similar features

## Reuse Patterns

If you need to verify similar functionality in the future:

**For feature verification:**
1. Create a temporary `verify_<feature>.py` script
2. Run it to validate the implementation
3. Add equivalent tests to `tests/` directory
4. Archive the verification script here
5. Document results in relevant MODULE or feature .md file

**For ongoing validation:**
- Use `tests/` directory for automated regression tests
- Use `validation/` for invariant checks and safety suites
- Use `examples/` for demonstrational/tutorial scripts

## Running Archived Scripts

If you need to re-run an archived script:

```bash
# From repository root
python scripts/archived_verification/verify_symbol_fix.py
python scripts/archived_verification/verify_module_27_patches.py
python scripts/archived_verification/verify_flatten_shutdown.py
python scripts/archived_verification/verify_config_backtest.py
```

**Note:** These scripts may fail if the codebase has evolved significantly since archival.

## Total Impact

- **Files archived:** 4
- **Lines archived:** 829 total
  - verify_symbol_fix.py: 157 lines
  - verify_module_27_patches.py: 231 lines
  - verify_flatten_shutdown.py: 217 lines
  - verify_config_backtest.py: 224 lines
- **Root directory cleanup:** -4 files
- **Risk:** Zero (no active code dependencies)
